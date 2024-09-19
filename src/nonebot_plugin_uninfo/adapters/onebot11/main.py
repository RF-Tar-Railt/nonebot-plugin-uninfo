from datetime import datetime, timedelta
from typing import Optional, Union

from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import (
    FriendAddNoticeEvent,
    FriendRecallNoticeEvent,
    FriendRequestEvent,
    GroupAdminNoticeEvent,
    GroupBanNoticeEvent,
    GroupDecreaseNoticeEvent,
    GroupIncreaseNoticeEvent,
    GroupMessageEvent,
    GroupRecallNoticeEvent,
    GroupRequestEvent,
    GroupUploadNoticeEvent,
    HonorNotifyEvent,
    PokeNotifyEvent,
    PrivateMessageEvent,
)
from nonebot.exception import ActionFailed

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.fetch import SuppliedData
from nonebot_plugin_uninfo.model import Member, MuteInfo, Role, Scene, SceneType, User

ROLES = {
    "owner": ("OWNER", 100),
    "admin": ("ADMINISTRATOR", 10),
    "member": ("MEMBER", 1),
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            nick=data["nickname"],
            avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['user_id']}&s=640",
            gender=data.get("gender", "unknown"),
        )

    def extract_scene(self, data):
        if "group_id" not in data:
            return Scene(
                id=data["user_id"],
                type=SceneType.PRIVATE,
                name=data["name"],
                avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['user_id']}&s=640",
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
                role=Role(*ROLES[_role], name=_role) if (_role := data.get("role")) else None,
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
            role=Role(*ROLES[_role], name=_role) if (_role := data.get("role")) else None,
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
                "user_id": str(friend["user_id"]),
                "name": friend["nickname"],
                "nickname": friend["remark"],
            }
            yield self.extract_user(data)

    async def query_scene(self, bot: Bot, guild_id: Optional[str]):
        groups = await bot.get_group_list()
        for group in groups:
            if not guild_id or str(group["group_id"]) == guild_id:
                data = {
                    "group_id": str(group["group_id"]),
                    "group_name": group["group_name"],
                }
                yield self.extract_scene(data)

    async def query_member(self, bot: Bot, guild_id: str):
        members = await bot.get_group_member_list(group_id=int(guild_id))
        for member in members:
            data = {
                "group_id": str(guild_id),
                "user_id": str(member["user_id"]),
                "name": member["nickname"],
                "card": member["card"],
                "role": member["role"],
                "join_time": member.get("join_time"),
                "gender": member["sex"],
            }
            yield self.extract_member(data, None)

    def supply_self(self, bot: Bot) -> SuppliedData:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.onebot11,
            "scope": SupportScope.qq_client,
        }


fetcher = InfoFetcher(SupportAdapter.onebot11)


@fetcher.supply
async def _(bot, event: PrivateMessageEvent):
    return {
        "user_id": str(event.user_id),
        "name": event.sender.nickname,
        "nickname": event.sender.card,
        "gender": event.sender.sex or "unknown",
    }


@fetcher.supply
async def _(bot, event: Union[FriendAddNoticeEvent, FriendRecallNoticeEvent, FriendRequestEvent]):
    async for friend in fetcher.query_user(bot):
        if friend.id == str(event.user_id):
            friend_info = {
                "nickname": friend.name,
                "remark": friend.nick,
            }
            break
    else:
        try:
            friend_info = await bot.get_stranger_info(user_id=event.user_id)
        except ActionFailed:
            friend_info = {}
    return {
        "user_id": str(event.user_id),
        "name": friend_info.get("nickname"),
        "nickname": friend_info.get("remark"),
        "gender": friend_info.get("sex", "unknown"),
    }


@fetcher.supply
async def _(bot, event: GroupMessageEvent):
    try:
        group_info = await bot.get_group_info(group_id=event.group_id)
    except ActionFailed:
        group_info = {}
    try:
        member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
    except ActionFailed:
        member_info = {}
    return {
        "group_id": str(event.group_id),
        "group_name": group_info.get("group_name"),
        "user_id": str(event.user_id),
        "name": event.sender.nickname,
        "nickname": event.sender.card,
        "card": member_info.get("card"),
        "role": event.sender.role,
        "join_time": member_info.get("join_time"),
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        GroupUploadNoticeEvent,
        GroupAdminNoticeEvent,
        GroupRequestEvent,
        HonorNotifyEvent,
    ],
):
    try:
        group_info = await bot.get_group_info(group_id=event.group_id)
    except ActionFailed:
        group_info = {}
    try:
        member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
    except ActionFailed:
        member_info = {}
    return {
        "group_id": str(event.group_id),
        "group_name": group_info.get("group_name"),
        "user_id": str(event.user_id),
        "name": member_info.get("nickname"),
        "nickname": member_info.get("card"),
        "card": member_info.get("card"),
        "role": member_info.get("role"),
        "join_time": member_info.get("join_time"),
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: PokeNotifyEvent,
):
    if not event.group_id:
        async for friend in fetcher.query_user(bot):
            if friend.id == str(event.user_id):
                friend_info = {
                    "nickname": friend.name,
                    "remark": friend.nick,
                }
                break
        else:
            try:
                friend_info = await bot.get_stranger_info(user_id=event.user_id)
            except ActionFailed:
                friend_info = {}
        return {
            "user_id": str(event.user_id),
            "name": friend_info.get("nickname"),
            "nickname": friend_info.get("remark"),
            "gender": friend_info.get("sex", "unknown"),
        }
    try:
        group_info = await bot.get_group_info(group_id=event.group_id)
    except ActionFailed:
        group_info = {}
    try:
        operator_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
    except ActionFailed:
        operator_info = {}
    try:
        member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.target_id, no_cache=True)
    except ActionFailed:
        member_info = {}
    return {
        "group_id": str(event.group_id),
        "group_name": group_info.get("group_name"),
        "user_id": str(event.target_id),
        "name": member_info.get("nickname"),
        "nickname": member_info.get("card"),
        "card": member_info.get("card"),
        "role": member_info.get("role"),
        "join_time": member_info.get("join_time"),
        "operator": {
            "group_id": str(event.group_id),
            "user_id": str(event.user_id),
            "name": operator_info.get("nickname"),
            "nickname": operator_info.get("card"),
            "card": operator_info.get("card"),
            "role": operator_info.get("role"),
            "join_time": operator_info.get("join_time"),
        },
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        GroupDecreaseNoticeEvent,
        GroupIncreaseNoticeEvent,
        GroupRecallNoticeEvent,
    ],
):
    try:
        group_info = await bot.get_group_info(group_id=event.group_id)
    except ActionFailed:
        group_info = {}
    try:
        member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
    except ActionFailed:
        member_info = {}
    try:
        operator_info = await bot.get_group_member_info(
            group_id=event.group_id, user_id=event.operator_id, no_cache=True
        )
    except ActionFailed:
        operator_info = {}
    return {
        "group_id": str(event.group_id),
        "group_name": group_info.get("group_name"),
        "user_id": str(event.user_id),
        "name": member_info.get("nickname"),
        "nickname": member_info.get("card"),
        "card": member_info.get("card"),
        "role": member_info.get("role"),
        "join_time": member_info.get("join_time"),
        "operator": {
            "group_id": str(event.group_id),
            "user_id": str(event.operator_id),
            "name": operator_info.get("nickname"),
            "nickname": operator_info.get("card"),
            "card": operator_info.get("card"),
            "role": operator_info.get("role"),
            "join_time": operator_info.get("join_time"),
        },
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: GroupBanNoticeEvent,
):
    try:
        group_info = await bot.get_group_info(group_id=event.group_id)
    except ActionFailed:
        group_info = {}
    try:
        member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
    except ActionFailed:
        member_info = {}
    try:
        operator_info = await bot.get_group_member_info(
            group_id=event.group_id, user_id=event.operator_id, no_cache=True
        )
    except ActionFailed:
        operator_info = {}
    return {
        "group_id": str(event.group_id),
        "group_name": group_info.get("group_name"),
        "user_id": str(event.user_id),
        "name": member_info.get("nickname"),
        "nickname": member_info.get("card"),
        "card": member_info.get("card"),
        "role": member_info.get("role"),
        "join_time": member_info.get("join_time"),
        "mute_duration": event.duration,
        "operator": {
            "group_id": str(event.group_id),
            "user_id": str(event.operator_id),
            "name": operator_info.get("nickname"),
            "nickname": operator_info.get("card"),
            "card": operator_info.get("card"),
            "role": operator_info.get("role"),
            "join_time": operator_info.get("join_time"),
        },
    }
