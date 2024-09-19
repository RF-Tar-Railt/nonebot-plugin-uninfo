from datetime import timedelta
from typing import Optional, Union

from nonebot.adapters.onebot.v12 import Bot
from nonebot.adapters.onebot.v12.event import (
    ChannelCreateEvent,
    ChannelDeleteEvent,
    ChannelMemberDecreaseEvent,
    ChannelMemberIncreaseEvent,
    ChannelMessageDeleteEvent,
    ChannelMessageEvent,
    FriendDecreaseEvent,
    FriendIncreaseEvent,
    GroupMemberDecreaseEvent,
    GroupMemberIncreaseEvent,
    GroupMessageDeleteEvent,
    GroupMessageEvent,
    GuildMemberDecreaseEvent,
    GuildMemberIncreaseEvent,
    PrivateMessageDeleteEvent,
    PrivateMessageEvent,
)
from nonebot.exception import ActionFailed

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.fetch import SuppliedData
from nonebot_plugin_uninfo.model import Member, MuteInfo, Scene, SceneType, User


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            nick=data["nickname"],
        )

    def extract_scene(self, data):
        if "group_id" in data:
            return Scene(
                id=data["group_id"],
                type=SceneType.GROUP,
                name=data.get("group_name"),
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
        return Scene(
            id=data["user_id"],
            type=SceneType.PRIVATE,
        )

    def extract_member(self, data, user: Optional[User]):
        if "group_id" not in data:
            return None
        if "guild_id" not in data:
            return None
        if user:
            return Member(
                user=user,
                nick=data["displayname"],
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
            ),
            nick=data["displayname"],
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
                "user_id": friend["user_id"],
                "name": friend["user_name"],
                "nickname": friend["user_remark"],
            }
            yield self.extract_user(data)

    async def query_scene(self, bot: Bot, guild_id: Optional[str]):
        groups = await bot.get_group_list()
        for group in groups:
            data = {
                "group_id": group["group_id"],
                "group_name": group["group_name"],
            }
            if not guild_id or group["group_id"] == guild_id:
                yield self.extract_scene(data)
        guilds = await bot.get_guild_list()
        for guild in guilds:
            data = {
                "guild_id": guild["guild_id"],
                "guild_name": guild["guild_name"],
            }
            if not guild_id or guild["guild_id"] == guild_id:
                yield self.extract_scene(data)
                channels = await bot.get_channel_list(guild_id=guild["guild_id"])
                for channel in channels:
                    data = {
                        "guild_id": guild["guild_id"],
                        "guild_name": guild["guild_name"],
                        "channel_id": channel["channel_id"],
                        "channel_name": channel["channel_name"],
                    }
                    yield self.extract_scene(data)

    async def query_member(self, bot: Bot, guild_id: str):
        try:
            group_members = await bot.get_group_member_list(group_id=guild_id)
        except ActionFailed:
            group_members = []
        for member in group_members:
            data = {
                "group_id": guild_id,
                "user_id": member["user_id"],
                "name": member["user_name"],
                "displayname": member["user_displayname"],
            }
            yield self.extract_member(data, None)
        try:
            guild_members = await bot.get_guild_member_list(guild_id=guild_id)
        except ActionFailed:
            guild_members = []
        for member in guild_members:
            data = {
                "guild_id": guild_id,
                "user_id": member["user_id"],
                "name": member["user_name"],
                "displayname": member["user_displayname"],
            }
            yield self.extract_member(data, None)

    def supply_self(self, bot: Bot) -> SuppliedData:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.onebot12,
            "scope": SupportScope.ensure_ob12(bot.platform),
        }


fetcher = InfoFetcher(SupportAdapter.onebot12)


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        PrivateMessageDeleteEvent,
        PrivateMessageEvent,
        FriendDecreaseEvent,
        FriendIncreaseEvent,
    ],
):
    try:
        user_info = await bot.get_user_info(user_id=event.user_id)
    except ActionFailed:
        user_info = {}
    return {
        "user_id": event.user_id,
        "name": user_info.get("user_name"),
        "nickname": user_info.get("user_remark"),
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        GroupMemberDecreaseEvent,
        GroupMemberIncreaseEvent,
        GroupMessageDeleteEvent,
        GroupMessageEvent,
    ],
):
    try:
        group_info = await bot.get_group_info(group_id=event.group_id)
    except ActionFailed:
        group_info = {}
    try:
        user_info = await bot.get_user_info(user_id=event.user_id)
    except ActionFailed:
        user_info = {}
    try:
        member_info = await bot.get_group_member_info(
            group_id=event.group_id,
            user_id=event.user_id,
        )
    except ActionFailed:
        member_info = {}
    return {
        "group_id": event.group_id,
        "group_name": group_info.get("group_name"),
        "user_id": event.user_id,
        "name": user_info.get("user_name"),
        "nickname": user_info.get("user_remark"),
        "displayname": member_info.get("user_displayname"),
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        ChannelMemberDecreaseEvent,
        ChannelMemberIncreaseEvent,
        ChannelMessageDeleteEvent,
        ChannelMessageEvent,
    ],
):
    try:
        guild_info = await bot.get_group_info(group_id=event.guild_id)
    except ActionFailed:
        guild_info = {}
    try:
        channel_info = await bot.get_channel_info(guild_id=event.guild_id, channel_id=event.channel_id)
    except ActionFailed:
        channel_info = {}
    try:
        user_info = await bot.get_guild_member_info(guild_id=event.guild_id, user_id=event.user_id)
    except ActionFailed:
        user_info = {}
    try:
        member_info = await bot.get_channel_member_info(
            guild_id=event.guild_id,
            channel_id=event.channel_id,
            user_id=event.user_id,
        )
    except ActionFailed:
        member_info = {}
    return {
        "guild_id": event.guild_id,
        "guild_name": guild_info.get("guild_name"),
        "channel_id": event.channel_id,
        "channel_name": channel_info.get("channel_name"),
        "user_id": event.user_id,
        "name": user_info.get("user_name"),
        "nickname": user_info.get("user_displayname"),
        "displayname": member_info.get("user_displayname"),
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        ChannelCreateEvent,
        ChannelDeleteEvent,
    ],
):
    try:
        guild_info = await bot.get_group_info(group_id=event.guild_id)
    except ActionFailed:
        guild_info = {}
    try:
        channel_info = await bot.get_channel_info(guild_id=event.guild_id, channel_id=event.channel_id)
    except ActionFailed:
        channel_info = {}
    try:
        user_info = await bot.get_guild_member_info(guild_id=event.guild_id, user_id=event.operator_id)
    except ActionFailed:
        user_info = {}
    return {
        "guild_id": event.guild_id,
        "guild_name": guild_info.get("guild_name"),
        "channel_id": event.channel_id,
        "channel_name": channel_info.get("channel_name"),
        "user_id": event.operator_id,
        "name": user_info.get("user_name"),
        "nickname": user_info.get("user_displayname"),
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        GuildMemberDecreaseEvent,
        GuildMemberIncreaseEvent,
    ],
):
    try:
        guild_info = await bot.get_guild_info(guild_id=event.guild_id)
    except ActionFailed:
        guild_info = {}
    try:
        user_info = await bot.get_guild_member_info(guild_id=event.guild_id, user_id=event.user_id)
    except ActionFailed:
        user_info = {}
    try:
        operator_info = await bot.get_guild_member_info(guild_id=event.guild_id, user_id=event.operator_id)
    except ActionFailed:
        operator_info = {}
    return {
        "guild_id": event.guild_id,
        "guild_name": guild_info.get("guild_name"),
        "user_id": event.user_id,
        "name": user_info.get("user_name"),
        "nickname": user_info.get("user_displayname"),
        "operator": {
            "guild_id": event.guild_id,
            "guild_name": guild_info.get("guild_name"),
            "user_id": event.operator_id,
            "name": operator_info.get("user_name"),
            "nickname": operator_info.get("user_displayname"),
        },
    }
