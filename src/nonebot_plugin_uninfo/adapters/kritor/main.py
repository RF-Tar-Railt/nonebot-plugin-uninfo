from datetime import datetime, timedelta
from typing import Optional, Union

from nonebot.adapters.kritor import Bot
from nonebot.adapters.kritor.event import (
    FriendApplyRequest,
    FriendMessage,
    GroupApplyRequest,
    GroupMessage,
    GuildMessage,
    InvitedJoinGroupRequest,
    NearbyMessage,
    StrangerMessage,
    TempMessage,
)
from nonebot.exception import ActionFailed

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, MuteInfo, Role, Scene, SceneType, User

ROLES = {
    "owner": ("OWNER", 100),
    "admin": ("ADMINISTRATOR", 10),
    "member": ("MEMBER", 1),
    "unknown": ("UNKNOWN", 0),
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            nick=data["nickname"],
            avatar=data.get("avatar", f"http://q1.qlogo.cn/g?b=qq&nk={data['user_id']}&s=640"),
        )

    def extract_scene(self, data):
        if "group_id" in data:
            return Scene(
                id=data["group_id"],
                type=SceneType.GROUP,
                name=data.get("group_name"),
                avatar=f"https://p.qlogo.cn/gh/{data['group_id']}/{data['group_id']}/",
            )
        if "guild_id" in data:
            if "channel_id" in data:
                return Scene(
                    id=data["channel_id"],
                    type=SceneType.CHANNEL_TEXT,
                    name=data["channel_name"],
                    parent=Scene(
                        id=data["guild_id"],
                        type=SceneType.GUILD,
                        name=data.get("guild_name"),
                    ),
                )
            return Scene(
                id=data["guild_id"],
                type=SceneType.GUILD,
                name=data.get("guild_name"),
            )
        if "parent_group_id" in data:
            return Scene(
                id=data["user_id"],
                type=SceneType.PRIVATE,
                avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['user_id']}&s=640",
                parent=Scene(
                    id=data["parent_group_id"],
                    type=SceneType.GROUP,
                    name=data.get("parent_group_name"),
                    avatar=f"https://p.qlogo.cn/gh/{data['parent_group_id']}/{data['parent_group_id']}/",
                ),
            )
        return Scene(
            id=data["user_id"],
            type=SceneType.PRIVATE,
            avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['user_id']}&s=640",
        )

    def extract_member(self, data, user: Optional[User]):
        if "group_id" not in data or "guild_id" not in data:
            return None
        if user:
            return Member(
                user=user,
                nick=data["card"],
                mute=(
                    MuteInfo(muted=True, duration=timedelta(seconds=data["mute_duration"]))
                    if "mute_duration" in data
                    else None
                ),
                joined_at=datetime.fromtimestamp(data["join_time"]) if "join_time" in data else None,
                role=Role(*ROLES[data["role"]], data["role"]) if "role" in data else None,
            )
        return Member(
            User(
                id=data["user_id"],
                name=data["name"],
                nick=data.get("nickname"),
                avatar=data.get("avatar", f"https://q2.qlogo.cn/headimg_dl?dst_uin={data['user_id']}&spec=640"),
            ),
            nick=data["card"],
            mute=(
                MuteInfo(muted=True, duration=timedelta(seconds=data["mute_duration"]))
                if "mute_duration" in data
                else None
            ),
            joined_at=datetime.fromtimestamp(data["join_time"]) if "join_time" in data else None,
            role=Role(*ROLES[data["role"]], data["role"]) if "role" in data else None,
        )

    async def query_user(self, bot: Bot, user_id: str):
        try:
            profile = (await bot.get_friend_profile_card(targets=[int(user_id)])).friends_profile_card[0]
        except ActionFailed:
            profile = (await bot.get_stranger_profile_card(targets=[int(user_id)])).strangers_profile_card[0]
        data = {
            "user_id": profile.uin,
            "name": profile.nick,
            "nickname": profile.remark,
        }
        return self.extract_user(data)

    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type == SceneType.GROUP:
            group = await bot.get_group_info(group=scene_id)
            return self.extract_scene(
                {
                    "group_id": group.group_id,
                    "group_name": group.group_name,
                }
            )

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        if scene_type == SceneType.GROUP:
            group_id = parent_scene_id

            member_info = await bot.get_group_member_info(group=group_id, target=user_id)
            group_info = await bot.get_group_info(group=group_id)
            data = {
                "group_id": group_id,
                "user_id": member_info.uin,
                "name": member_info.nick,
                "card": member_info.card,
                "mute_duration": member_info.shut_up_time,
                "join_time": member_info.join_time / 1000,
                "role": (
                    "owner"
                    if member_info.uin == group_info.owner
                    else "admin" if member_info.uin in group_info.admins else "member"
                ),
            }
            return self.extract_member(data, None)

        elif scene_type == SceneType.GUILD:
            guild_id = parent_scene_id

            member = await bot.get_guild_member(guild_id=guild_id, tiny_id=int(user_id))
            data = {
                "guild_id": guild_id,
                "user_id": member.member_info.tiny_id,
                "name": member.member_info.nickname,
                "card": member.member_info.nickname,
                "join_time": member.member_info.join_time / 1000,
                "role": member.member_info.roles_info[0].role_name.lower(),
                "avatar": member.member_info.avatar_url,
            }
            return self.extract_member(data, None)

    async def query_users(self, bot: Bot):
        friends = await bot.get_friend_list()
        for friend in friends:
            data = {
                "user_id": friend.uin,
                "name": friend.nick,
                "nickname": friend.remark,
            }
            yield self.extract_user(data)

    async def query_scenes(
        self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type is None or scene_type == SceneType.PRIVATE:
            async for user in self.query_users(bot):
                yield self.extract_scene(
                    {
                        "user_id": user.id,
                        "name": user.name,
                        "avatar": user.avatar,
                    }
                )
            if scene_type == SceneType.PRIVATE:
                return

        if scene_type is None or scene_type == SceneType.GROUP:
            groups = await bot.get_group_list()
            for group in groups:
                yield self.extract_scene(
                    {
                        "group_id": group.group_id,
                        "group_name": group.group_name,
                    }
                )
            if scene_type == SceneType.GROUP:
                return

        guilds = await bot.get_guild_list()
        for guild in guilds:
            if parent_scene_id is None or guild.guild_id == parent_scene_id:
                data = {
                    "guild_id": guild.guild_id,
                    "guild_name": guild.guild_name,
                }
                if scene_type is None or scene_type == SceneType.GUILD:
                    yield self.extract_scene(data)
                if scene_type == SceneType.GUILD:
                    continue
                channels = await bot.get_guild_channel_list(guild_id=guild.guild_id)
                for channel in channels:
                    data = {
                        "guild_id": guild.guild_id,
                        "guild_name": guild.guild_name,
                        "channel_id": channel.channel_id,
                        "channel_name": channel.channel_name,
                    }
                    yield self.extract_scene(data)

    async def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        if scene_type == SceneType.GROUP:
            group_id = parent_scene_id
            group_members = await bot.get_group_member_list(group=group_id)
            group_info = await bot.get_group_info(group=group_id)
            admins = group_info.admins
            owner = [group_info.owner]
            for member in group_members:
                data = {
                    "group_id": group_id,
                    "user_id": member.uin,
                    "name": member.nick,
                    "card": member.card,
                    "mute_duration": member.shut_up_time,
                    "join_time": member.join_time / 1000,
                    "role": "owner" if member.uin in owner else "admin" if member.uin in admins else "member",
                }
                yield self.extract_member(data, None)

        elif scene_type == SceneType.GUILD:
            guild_id = parent_scene_id
            guild_members = await bot.get_guild_member_list(guild_id=guild_id)
            for member in guild_members.members_info:
                try:
                    member_prof = await bot.get_guild_member(guild_id=guild_id, tiny_id=member.tiny_id)
                    avatar = member_prof.member_info.avatar_url
                except ActionFailed:
                    avatar = None
                data = {
                    "guild_id": guild_id,
                    "user_id": member.tiny_id,
                    "name": member.nickname,
                    "card": member.nickname,
                    "join_time": member.join_time / 1000,
                    "role": member.role_name.lower(),
                    "avatar": avatar,
                }
                yield self.extract_member(data, None)
            while guild_members.next_token and not guild_members.finished:
                guild_members = await bot.get_guild_member_list(guild_id=guild_id, next_token=guild_members.next_token)
                for member in guild_members.members_info:
                    try:
                        member_prof = await bot.get_guild_member(guild_id=guild_id, tiny_id=member.tiny_id)
                        avatar = member_prof.member_info.avatar_url
                    except ActionFailed:
                        avatar = None
                    data = {
                        "guild_id": guild_id,
                        "user_id": member.tiny_id,
                        "name": member.nickname,
                        "card": member.nickname,
                        "join_time": member.join_time / 1000,
                        "role": member.role_name.lower(),
                        "avatar": avatar,
                    }
                    yield self.extract_member(data, None)

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.kritor,
            "scope": SupportScope.qq_client,
        }


fetcher = InfoFetcher(SupportAdapter.kritor)


@fetcher.supply
async def _(bot: Bot, event: FriendMessage):
    try:
        user_info = await bot.get_friend_profile_card(targets=[event.sender.uin])
        remark = user_info.friends_profile_card[0].remark
    except ActionFailed:
        user_info = {}
        remark = None
    return {
        "user_id": event.sender.uin,
        "name": event.sender.nick,
        "nickname": remark,
    }


@fetcher.supply
async def _(bot: Bot, event: GroupMessage):
    try:
        group_info = await bot.get_group_info(group=event.sender.group_id)
        member_info = await bot.get_group_member_info(group=event.sender.group_id, target=event.sender.uin)
        nick = member_info.nick
        card = member_info.card
        group_name = group_info.group_name
        group_admins = group_info.admins
        group_owner = group_info.owner
        extra = {
            "mute_duration": member_info.shut_up_time,
            "join_time": member_info.join_time / 1000,
            "role": (
                "owner"
                if event.sender.uin == group_owner
                else "admin" if event.sender.uin in group_admins else "member"
            ),
        }
    except ActionFailed:
        nick = card = event.sender.nick
        group_name = ""
        extra = {}
    return {
        "user_id": event.sender.uin,
        "group_id": event.sender.group_id,
        "name": nick,
        "card": card,
        "group_name": group_name,
        **extra,
    }


@fetcher.supply
async def _(bot: Bot, event: Union[StrangerMessage, NearbyMessage]):
    try:
        user_info = await bot.get_stranger_profile_card(targets=[event.sender.uin])
        remark = user_info.strangers_profile_card[0].remark
    except ActionFailed:
        remark = None
    return {
        "user_id": event.sender.uin,
        "name": event.sender.nick,
        "nickname": remark,
    }


@fetcher.supply
async def _(bot: Bot, event: TempMessage):
    try:
        group_info = await bot.get_group_info(group=event.sender.group_id)
        member_info = await bot.get_group_member_info(group=event.sender.group_id, target=event.sender.uin)
        nick = member_info.nick
        card = member_info.card
        group_name = group_info.group_name
        group_admins = group_info.admins
        group_owner = group_info.owner
        extra = {
            "mute_duration": member_info.shut_up_time,
            "join_time": member_info.join_time / 1000,
            "role": (
                "owner"
                if event.sender.uin == group_owner
                else "admin" if event.sender.uin in group_admins else "member"
            ),
        }
    except ActionFailed:
        nick = card = event.sender.nick
        group_name = ""
        extra = {}
    return {
        "user_id": event.sender.uin,
        "parent_group_id": event.sender.group_id,
        "name": nick,
        "card": card,
        "parent_group_name": group_name,
        **extra,
    }


@fetcher.supply
async def _(bot: Bot, event: GuildMessage):
    try:
        guilds = await bot.get_guild_list()
        guild_info = next(guild for guild in guilds if guild.guild_id == event.sender.guild_id)
        guild_name = guild_info.guild_name
        channels = await bot.get_guild_channel_list(guild_id=event.sender.guild_id)
        channel_info = next(channel for channel in channels if channel.channel_id == event.sender.channel_id)
        channel_name = channel_info.channel_name
    except (ActionFailed, StopIteration):
        guild_name = ""
        channel_name = ""
    try:
        member = await bot.get_guild_member(guild_id=event.sender.guild_id, tiny_id=int(event.sender.tiny_id))
        card = member.member_info.nickname
        extra = {
            "avatar": member.member_info.avatar_url,
            "join_time": member.member_info.join_time / 1000,
        }
    except (ActionFailed, StopIteration):
        card = event.sender.nick
        extra = {}
    return {
        "user_id": event.sender.tiny_id,
        "name": event.sender.nick,
        "card": card,
        "guild_id": event.sender.guild_id,
        "guild_name": guild_name,
        "channel_id": event.sender.channel_id,
        "channel_name": channel_name,
        "role": event.sender.role.name.lower(),
        **extra,
    }


@fetcher.supply
async def _(bot: Bot, event: GroupApplyRequest):
    try:
        user_info = await bot.get_stranger_profile_card(targets=[event.applier_uin])
        nick = user_info.strangers_profile_card[0].nick
        remark = user_info.strangers_profile_card[0].remark
    except ActionFailed:
        nick = ""
        remark = None
    try:
        group_info = await bot.get_group_info(group=event.group_id)
        group_name = group_info.group_name
    except ActionFailed:
        group_name = ""
    return {
        "user_id": event.applier_uin,
        "name": nick,
        "nickname": remark,
        "group_id": event.group_id,
        "group_name": group_name,
    }


@fetcher.supply
async def _(bot: Bot, event: FriendApplyRequest):
    try:
        user_info = await bot.get_stranger_profile_card(targets=[event.applier_uin])
        nick = user_info.strangers_profile_card[0].nick
        remark = user_info.strangers_profile_card[0].remark
    except ActionFailed:
        nick = ""
        remark = None
    return {
        "user_id": event.applier_uin,
        "name": nick,
        "nickname": remark,
    }


@fetcher.supply
async def _(bot: Bot, event: InvitedJoinGroupRequest):
    try:
        user_info = await bot.get_stranger_profile_card(targets=[event.inviter_uin])
        nick = user_info.strangers_profile_card[0].nick
        remark = user_info.strangers_profile_card[0].remark
    except ActionFailed:
        nick = ""
        remark = None
    try:
        group_info = await bot.get_group_info(group=event.group_id)
        group_name = group_info.group_name
    except ActionFailed:
        group_name = ""
    return {
        "user_id": event.inviter_uin,
        "name": nick,
        "nickname": remark,
        "group_id": event.group_id,
        "group_name": group_name,
    }
