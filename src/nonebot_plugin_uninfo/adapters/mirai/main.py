from datetime import datetime, timedelta
from typing import Optional, Union

from nonebot.adapters.mirai import Bot
from nonebot.adapters.mirai.event import (
    BotInvitedJoinGroupRequestEvent,
    BotJoinGroupEvent,
    BotLeaveEventDisband,
    BotLeaveEventKick,
    BotMuteEvent,
    BotUnmuteEvent,
    FriendAddEvent,
    FriendDeleteEvent,
    FriendInputStatusChangedEvent,
    FriendMessage,
    FriendNickChangedEvent,
    FriendRecallEvent,
    GroupAllowMemberInviteEvent,
    GroupEntranceAnnouncementChangeEvent,
    GroupMessage,
    GroupMuteAllEvent,
    GroupNameChangeEvent,
    GroupRecallEvent,
    MemberCardChangeEvent,
    MemberHonorChangeEvent,
    MemberJoinEvent,
    MemberJoinRequestEvent,
    MemberLeaveEventKick,
    MemberLeaveEventQuit,
    MemberMuteEvent,
    MemberPermissionChangeEvent,
    MemberSpecialTitleChangeEvent,
    MemberUnmuteEvent,
    NewFriendRequestEvent,
    NudgeEvent,
    StrangerMessage,
    TempMessage,
)
from nonebot.adapters.mirai.model.relationship import Group, MemberPerm
from nonebot.exception import ActionFailed

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.fetch import SuppliedData
from nonebot_plugin_uninfo.model import Member, MuteInfo, Role, Scene, SceneType, User

ROLES = {
    MemberPerm.Owner: Role("OWNER", 100, "OWNER"),
    MemberPerm.Administrator: Role("ADMINISTRATOR", 10, "ADMINISTRATOR"),
    MemberPerm.Member: Role("MEMBER", 1, "MEMBER"),
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            nick=data.get("nickname"),
            avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['user_id']}&s=640",
            gender=data.get("gender", "unknown"),
        )

    def extract_scene(self, data):
        if "group_id" not in data:
            return Scene(
                id=data["user_id"],
                type=SceneType.PRIVATE,
            )
        return Scene(
            id=data["group_id"],
            type=SceneType.GROUP,
            name=data["group_name"],
            avatar=f"https://p.qlogo.cn/gh/{data['group_id']}/{data['group_id']}/",
        )

    def extract_member(self, data, user: Optional[User]):
        if "group_id" not in data:
            return None
        if user:
            return Member(
                user=user,
                nick=data["card"],
                role=ROLES[_role] if (_role := data.get("role")) else None,
                joined_at=datetime.fromtimestamp(data["join_time"]) if data["join_time"] else None,
                mute=(
                    MuteInfo(muted=True, duration=timedelta(seconds=data["mute_duration"]))
                    if "mute_duration" in data
                    else None
                ),
            )
        return Member(
            User(
                id=data["user_id"],
                name=data["name"],
                nick=data.get("nickname"),
                avatar=f"https://q2.qlogo.cn/headimg_dl?dst_uin={data['user_id']}&spec=640",
            ),
            nick=data["card"],
            role=ROLES[_role] if (_role := data.get("role")) else None,
            joined_at=datetime.fromtimestamp(data["join_time"]) if data["join_time"] else None,
            mute=(
                MuteInfo(muted=True, duration=timedelta(seconds=data["mute_duration"]))
                if "mute_duration" in data
                else None
            ),
        )

    async def query_user(self, bot: Bot):
        friends = await bot.get_friend_list()
        for friend in friends:
            data = {
                "user_id": str(friend.id),
                "name": friend.nickname,
                "nickname": friend.remark,
            }
            yield self.extract_user(data)

    async def query_scene(self, bot: Bot, guild_id: Optional[str]):
        groups = await bot.get_group_list()
        for group in groups:
            if not guild_id or str(group.id) == guild_id:
                data = {
                    "group_id": str(group.id),
                    "group_name": group.name,
                }
                yield self.extract_scene(data)

    async def query_member(self, bot: Bot, guild_id: str):
        members = await bot.get_member_list(group=int(guild_id))
        for member in members:
            try:
                info = await bot.get_member_profile(group=int(guild_id), member=member.id)
                data = {
                    "group_id": str(guild_id),
                    "user_id": str(member.id),
                    "name": info.nickname,
                    "card": member.name,
                    "role": member.permission,
                    "join_time": member.join_timestamp,
                    "gender": info.sex.lower(),
                    "mute_duration": member.mute_time,
                }
            except ActionFailed:
                data = {
                    "group_id": str(guild_id),
                    "user_id": str(member.id),
                    "name": member.name,
                    "card": member.name,
                    "role": member.permission,
                    "join_time": member.join_timestamp,
                    "mute_duration": member.mute_time,
                }
            yield self.extract_member(data, None)

    def supply_self(self, bot: Bot) -> SuppliedData:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.mirai,
            "scope": SupportScope.qq_client,
        }


fetcher = InfoFetcher(SupportAdapter.mirai)


@fetcher.supply
async def _(bot: Bot, event: FriendMessage):
    try:
        info = await bot.get_friend_profile(friend=event.sender)
        sex = info.sex.lower()
    except ActionFailed:
        sex = "unknown"
    return {
        "user_id": str(event.sender.id),
        "name": event.sender.nickname,
        "nickname": event.sender.remark,
        "gender": sex,
    }


@fetcher.supply
async def _(bot: Bot, event: StrangerMessage):
    try:
        info = await bot.get_user_profile(target=event.sender)
        sex = info.sex.lower()
    except ActionFailed:
        sex = "unknown"
    return {
        "user_id": str(event.sender.id),
        "name": event.sender.nickname,
        "nickname": event.sender.remark,
        "gender": sex,
    }


@fetcher.supply
async def _(bot: Bot, event: Union[GroupMessage, TempMessage]):
    try:
        member_info = await bot.get_member_profile(group=event.group.id, member=event.sender.id)
        nickname = member_info.nickname
    except ActionFailed:
        nickname = event.sender.name
    return {
        "group_id": str(event.group.id),
        "group_name": event.group.name,
        "user_id": str(event.sender.id),
        "name": nickname,
        "card": event.sender.name,
        "role": event.sender.permission,
        "join_time": event.sender.join_timestamp,
        "mute_duration": event.sender.mute_time,
    }


@fetcher.supply
async def _(bot: Bot, event: BotJoinGroupEvent):
    self_info = await bot.get_bot_profile()
    if not event.inviter:
        return {
            "user_id": str(bot.self_id),
            "name": self_info.nickname,
            "card": self_info.nickname,
            "role": event.group.account_perm,
        }
    try:
        inviter_info = await bot.get_member_profile(group=event.group.id, member=event.inviter.id)
        nickname = inviter_info.nickname
    except ActionFailed:
        nickname = event.inviter.name
    return {
        "group_id": str(event.group.id),
        "group_name": event.group.name,
        "user_id": str(bot.self_id),
        "name": self_info.nickname,
        "card": self_info.nickname,
        "role": event.group.account_perm,
        "operator": {
            "user_id": str(event.inviter.id),
            "name": nickname,
            "card": event.inviter.name,
            "role": event.inviter.permission,
            "join_time": event.inviter.join_timestamp,
            "mute_duration": event.inviter.mute_time,
        },
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        BotMuteEvent,
        BotUnmuteEvent,
        BotLeaveEventKick,
        BotLeaveEventDisband,
        GroupNameChangeEvent,
        GroupEntranceAnnouncementChangeEvent,
        GroupMuteAllEvent,
        GroupAllowMemberInviteEvent,
    ],
):
    self_info = await bot.get_bot_profile()
    if not event.operator:
        return {
            "user_id": str(bot.self_id),
            "name": self_info.nickname,
            "card": self_info.nickname,
            "role": event.group.account_perm,
        }
    try:
        operator_info = await bot.get_member_profile(group=event.group.id, member=event.operator.id)
        nickname = operator_info.nickname
    except ActionFailed:
        nickname = event.operator.name
    return {
        "group_id": str(event.group.id),
        "group_name": event.group.name,
        "user_id": str(bot.self_id),
        "name": self_info.nickname,
        "card": self_info.nickname,
        "role": event.group.account_perm,
        "mute_duration": getattr(event, "duration", 0),
        "operator": {
            "user_id": str(event.operator.id),
            "name": nickname,
            "card": event.operator.name,
            "role": event.operator.permission,
            "join_time": event.operator.join_timestamp,
            "mute_duration": event.operator.mute_time,
        },
    }


@fetcher.supply
async def _(
    bot: Bot, event: Union[FriendAddEvent, FriendDeleteEvent, FriendInputStatusChangedEvent, FriendNickChangedEvent]
):
    return {
        "user_id": str(event.friend.id),
        "name": event.friend.nickname,
        "nickname": event.friend.remark,
    }


@fetcher.supply
async def _(bot: Bot, event: FriendRecallEvent):
    try:
        info = await bot.get_friend(target=event.operator)
    except ActionFailed:
        info = event.friend
    return {
        "user_id": str(info.id),
        "name": info.nickname,
        "nickname": info.remark,
    }


@fetcher.supply
async def _(bot: Bot, event: GroupRecallEvent):
    try:
        member = await bot.get_member(group=event.group.id, target=event.author_id)
        member_info = await bot.get_member_profile(group=event.group.id, member=event.author_id)
        name = member_info.nickname
        card = member.name
        role = member.permission
    except ActionFailed:
        name = ""
        card = ""
        role = MemberPerm.Member
    if not event.operator:
        return {
            "group_id": str(event.group.id),
            "group_name": event.group.name,
            "user_id": str(event.author_id),
            "name": name,
            "card": card,
            "role": role,
        }
    try:
        operator_info = await bot.get_member_profile(group=event.group.id, member=event.operator)
        nickname = operator_info.nickname
    except ActionFailed:
        nickname = event.operator.name
    return {
        "group_id": str(event.group.id),
        "group_name": event.group.name,
        "user_id": str(event.author_id),
        "name": name,
        "card": card,
        "role": role,
        "operator": {
            "user_id": str(event.operator),
            "name": nickname,
            "card": event.operator,
            "role": member.permission,
            "join_time": member.join_timestamp,
            "mute_duration": member.mute_time,
        },
    }


@fetcher.supply
async def _(bot: Bot, event: NudgeEvent):
    scene_type = event.scene
    if scene_type == "friend":
        try:
            info = await bot.get_friend(target=event.supplicant)
            name = info.nickname
            nickname = info.remark
        except ActionFailed:
            name = ""
            nickname = ""
        return {
            "user_id": str(event.supplicant),
            "name": name,
            "nickname": nickname,
        }
    if scene_type == "stranger":
        try:
            info = await bot.get_user_profile(target=event.supplicant)
            name = info.nickname
        except ActionFailed:
            name = ""
        return {
            "user_id": str(event.supplicant),
            "name": name,
        }
    if isinstance(event.subject, Group):
        try:
            member = await bot.get_member(group=event.subject.id, target=event.target)
            operator = await bot.get_member(group=event.subject.id, target=event.supplicant)
            member_info = await bot.get_member_profile(group=event.subject.id, member=event.target)
            operator_info = await bot.get_member_profile(group=event.subject.id, member=event.supplicant)
            name = member_info.nickname
            card = member.name
            role = member.permission
            operator_name = operator_info.nickname
            operator_card = operator.name
            operator_role = operator.permission
        except ActionFailed:
            name = ""
            card = ""
            role = MemberPerm.Member
            operator_name = ""
            operator_card = ""
            operator_role = MemberPerm.Member
        return {
            "group_id": str(event.subject.id),
            "group_name": event.subject.name,
            "user_id": str(event.target),
            "name": name,
            "card": card,
            "role": role,
            "operator": {
                "user_id": str(event.supplicant),
                "name": operator_name,
                "card": operator_card,
                "role": operator_role,
            },
        }
    raise NotImplementedError(f"Event {type(event)} not supported yet")


@fetcher.supply
async def _(bot: Bot, event: MemberJoinEvent):
    try:
        info = await bot.get_member_profile(group=event.group.id, member=event.member.id)
        name = info.nickname
    except ActionFailed:
        name = event.member.name
    if not event.inviter:
        return {
            "group_id": str(event.group.id),
            "group_name": event.group.name,
            "user_id": str(event.member.id),
            "name": name,
            "card": event.member.name,
            "role": event.member.permission,
            "join_time": event.member.join_timestamp,
            "mute_duration": event.member.mute_time,
        }
    try:
        inviter_info = await bot.get_member_profile(group=event.group.id, member=event.inviter.id)
        nickname = inviter_info.nickname
    except ActionFailed:
        nickname = event.inviter.name
    return {
        "group_id": str(event.group.id),
        "group_name": event.group.name,
        "user_id": str(event.member.id),
        "name": name,
        "card": event.member.name,
        "role": event.member.permission,
        "join_time": event.member.join_timestamp,
        "mute_duration": event.member.mute_time,
        "operator": {
            "user_id": str(event.inviter.id),
            "name": nickname,
            "card": event.inviter.name,
            "role": event.inviter.permission,
            "join_time": event.inviter.join_timestamp,
            "mute_duration": event.inviter.mute_time,
        },
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        MemberLeaveEventKick,
        MemberLeaveEventQuit,
        MemberCardChangeEvent,
        MemberSpecialTitleChangeEvent,
        MemberPermissionChangeEvent,
        MemberMuteEvent,
        MemberUnmuteEvent,
        MemberHonorChangeEvent,
    ],
):
    try:
        member_info = await bot.get_member_profile(group=event.group.id, member=event.member.id)
        name = member_info.nickname
    except ActionFailed:
        name = event.member.name
    if not (operator := getattr(event, "operator", None)):
        return {
            "group_id": str(event.group.id),
            "group_name": event.group.name,
            "user_id": str(event.member.id),
            "name": name,
            "card": event.member.name,
            "role": event.member.permission,
            "join_time": event.member.join_timestamp,
            "mute_duration": event.member.mute_time,
        }
    try:
        operator_info = await bot.get_member_profile(group=event.group.id, member=operator.id)
        nickname = operator_info.nickname
    except ActionFailed:
        nickname = operator.name
    return {
        "group_id": str(event.group.id),
        "group_name": event.group.name,
        "user_id": str(event.member.id),
        "name": name,
        "card": event.member.name,
        "role": event.member.permission,
        "join_time": event.member.join_timestamp,
        "mute_duration": event.member.mute_time,
        "operator": {
            "user_id": str(operator.id),
            "name": nickname,
            "card": operator.name,
            "role": operator.permission,
            "join_time": operator.join_timestamp,
            "mute_duration": operator.mute_time,
        },
    }


@fetcher.supply
async def _(bot: Bot, event: NewFriendRequestEvent):
    return {
        "user_id": str(event.supplicant),
        "name": event.nickname,
    }


@fetcher.supply
async def _(bot: Bot, event: Union[MemberJoinRequestEvent, BotInvitedJoinGroupRequestEvent]):
    return {
        "group_id": str(event.source_group),
        "group_name": event.group_name,
        "user_id": str(event.supplicant),
        "name": event.nickname,
    }
