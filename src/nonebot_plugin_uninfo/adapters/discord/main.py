from datetime import timedelta
from typing import Optional, Union

from nonebot.adapters.discord import Bot
from nonebot.adapters.discord.api.model import Channel as DiscordChannel
from nonebot.adapters.discord.api.model import GuildMember, Snowflake
from nonebot.adapters.discord.api.model import User as DiscordUser
from nonebot.adapters.discord.api.types import ChannelType as DiscordChannelType
from nonebot.adapters.discord.api.types import UNSET
from nonebot.adapters.discord.event import (
    ChannelCreateEvent,
    ChannelDeleteEvent,
    ChannelUpdateEvent,
    DirectMessageCreateEvent,
    DirectMessageDeleteBulkEvent,
    DirectMessageDeleteEvent,
    DirectMessageReactionAddEvent,
    DirectMessageReactionRemoveAllEvent,
    DirectMessageReactionRemoveEmojiEvent,
    DirectMessageReactionRemoveEvent,
    DirectMessageUpdateEvent,
    Event,
    GuildBanAddEvent,
    GuildBanRemoveEvent,
    GuildCreateEvent,
    GuildDeleteEvent,
    GuildMemberAddEvent,
    GuildMemberRemoveEvent,
    GuildMemberUpdateEvent,
    GuildMessageCreateEvent,
    GuildMessageDeleteBulkEvent,
    GuildMessageDeleteEvent,
    GuildMessageReactionAddEvent,
    GuildMessageReactionRemoveAllEvent,
    GuildMessageReactionRemoveEmojiEvent,
    GuildMessageReactionRemoveEvent,
    GuildMessageUpdateEvent,
    GuildUpdateEvent,
    InteractionCreateEvent,
)

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.fetch import SuppliedData
from nonebot_plugin_uninfo.model import Member, MuteInfo, Role, Scene, SceneType, User

CHANNEL_TYPE = {
    DiscordChannelType.GUILD_TEXT: SceneType.CHANNEL_TEXT,
    DiscordChannelType.GUILD_VOICE: SceneType.CHANNEL_VOICE,
    DiscordChannelType.GUILD_CATEGORY: SceneType.CHANNEL_CATEGORY,
    DiscordChannelType.DM: SceneType.PRIVATE,
    DiscordChannelType.GROUP_DM: SceneType.GROUP,
    DiscordChannelType.GUILD_STAGE_VOICE: SceneType.CHANNEL_VOICE,
    DiscordChannelType.GUILD_DIRECTORY: SceneType.CHANNEL_CATEGORY,
}

BASE_URL = "https://cdn.discordapp.com/"


def avatar_url(id: str, avatar: str):
    if not avatar:
        return None
    return f"{BASE_URL}avatars/{id}/{avatar}.png?size=1024"


async def _handle_role(bot: Bot, guild_id: str, roles: list[Snowflake]):
    if not roles:
        return Role("MEMBER", 1, "member")
    res = []
    resp = await bot.get_guild_roles(guild_id=int(guild_id))
    for role in resp:
        if role.id not in roles:
            continue
        perm = int(role.permissions)
        if perm & (1 << 3) == (1 << 3):
            if perm & (1 << 5) == (1 << 5):
                res.append(("OWNER", 100, role.name))
            res.append(("ADMINISTRATOR", 10, role.name))
        if perm & (1 << 4) == (1 << 4):
            res.append(("CHANNEL_ADMINISTRATOR", 9, role.name))
        res.append((str(role.id), 1, role.name))
    if not res:
        return Role("MEMBER", 1, "member")
    return Role(*sorted(res, key=lambda x: x[1], reverse=True)[0])


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            avatar=avatar_url(data["user_id"], data["avatar"]),
        )

    def extract_scene(self, data):
        if "guild_id" in data:
            if "channel_id" in data:
                return Scene(
                    id=data["channel_id"],
                    name=data.get("channel_name"),
                    type=data.get("channel_type", SceneType.CHANNEL_TEXT),
                    avatar=avatar_url(data["channel_id"], data.get("channel_avatar") or ""),
                    parent=Scene(
                        id=data["guild_id"],
                        name=data.get("guild_name"),
                        type=SceneType.GUILD,
                        avatar=avatar_url(data["guild_id"], data.get("guild_avatar") or ""),
                    ),
                )
            return Scene(
                id=data["guild_id"],
                name=data.get("guild_name"),
                type=SceneType.GUILD,
                avatar=avatar_url(data["guild_id"], data.get("guild_avatar") or ""),
            )
        if "channel_id" in data:
            return Scene(
                id=data["channel_id"],
                name=data.get("channel_name"),
                type=data.get("channel_type", SceneType.CHANNEL_TEXT),
                avatar=avatar_url(data["channel_id"], data.get("channel_avatar") or ""),
            )
        return Scene(
            id=data["user_id"],
            type=SceneType.PRIVATE,
            name=data["name"],
            avatar=avatar_url(data["user_id"], data.get("avatar") or ""),
        )

    def extract_member(self, data, user: Optional[User]):
        if "guild_id" in data or "channel_id" in data:
            if user:
                return Member(user, nick=data["nickname"], role=data.get("role"), joined_at=data.get("joined_at"))
            return Member(
                User(
                    id=data["user_id"],
                    name=data["name"],
                    avatar=avatar_url(data["user_id"], data.get("avatar") or ""),
                ),
                nick=data["nickname"],
                role=data.get("role"),
                joined_at=data.get("joined_at"),
            )
        return None

    async def query_user(self, bot: Bot):
        raise NotImplementedError

    async def query_scene(self, bot: Bot, guild_id: Optional[str]):
        guilds = await bot.get_current_user_guilds(limit=100)
        while guilds:
            for guild in guilds:
                if not guild_id or str(guild.id) == guild_id:
                    _guild = Scene(
                        id=str(guild.id),
                        type=SceneType.GUILD,
                        name=guild.name,
                        avatar=avatar_url(str(guild.id), guild.icon or ""),
                    )
                    yield _guild
                    channels = await bot.get_guild_channels(guild_id=guild.id)
                    for channel in channels:
                        yield Scene(
                            id=str(channel.id),
                            type=CHANNEL_TYPE.get(channel.type, SceneType.CHANNEL_TEXT),
                            name=channel.name,
                            avatar=avatar_url(str(channel.id), channel.icon or ""),
                            parent=_guild,
                        )
            if len(guilds) < 100:
                break
            guilds = await bot.get_current_user_guilds(limit=100, after=guilds[-1].id)

    async def query_member(self, bot: Bot, guild_id: str):
        members = await bot.list_guild_members(guild_id=int(guild_id), limit=100)
        while members:
            for member in members:
                if isinstance(member.user, DiscordUser):
                    user = User(
                        id=str(member.user.id),
                        name=member.user.username,
                        avatar=member.user.avatar,
                    )
                else:
                    continue
                yield Member(
                    user=user,
                    nick="" if member.nick is UNSET else member.nick,
                    role=await _handle_role(bot, guild_id, member.roles),
                    joined_at=member.joined_at,
                    mute=None if member.mute is UNSET else MuteInfo(muted=member.mute, duration=timedelta(60)),
                )
            if len(members) < 100:
                break
            members = await bot.list_guild_members(guild_id=int(guild_id), limit=100, after=members[-1].user.id)

    def supply_self(self, bot) -> SuppliedData:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.discord,
            "scope": SupportScope.discord,
        }


fetcher = InfoFetcher(SupportAdapter.discord)


@fetcher.supply
async def _(bot: Bot, event: InteractionCreateEvent):
    if isinstance(event.user, DiscordUser):
        base = {
            "user_id": str(event.user.id),
            "name": event.user.username,
            "nickname": "",
            "avatar": event.user.avatar,
        }
        return base
    assert isinstance(event.member, GuildMember)
    assert isinstance(event.guild_id, int)
    assert isinstance(event.channel_id, int)
    guild_info = await bot.get_guild(guild_id=event.guild_id)
    base = {
        "user_id": str(event.member.user.id),
        "name": event.member.user.username,
        "nickname": event.member.nick,
        "avatar": event.member.user.avatar,
        "guild_id": str(event.guild_id),
        "guild_name": guild_info.name,
        "guild_avatar": guild_info.icon,
    }
    if isinstance(event.channel, DiscordChannel):
        base |= {
            "channel_id": str(event.channel.id),
            "channel_name": event.channel.name or "",
            "channel_type": CHANNEL_TYPE.get(event.channel.type, SceneType.CHANNEL_TEXT),
            "channel_avatar": event.channel.icon or "",
        }
    else:
        channel = await bot.get_channel(channel_id=event.channel_id)
        base |= {
            "channel_id": str(channel.id),
            "channel_name": channel.name or "",
            "channel_type": CHANNEL_TYPE.get(channel.type, SceneType.CHANNEL_TEXT),
            "channel_avatar": channel.icon or "",
        }
    return base


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[DirectMessageCreateEvent, GuildMessageCreateEvent, DirectMessageUpdateEvent, GuildMessageUpdateEvent],
):
    base = {
        "user_id": str(event.author.id),
        "name": event.author.username,
        "nickname": event.author.username,
        "avatar": event.author.avatar,
    }
    if isinstance(event.guild_id, Snowflake):
        guild = await bot.get_guild(guild_id=int(event.guild_id))
        base |= {
            "guild_id": str(event.guild_id),
            "guild_name": guild.name,
            "guild_avatar": guild.icon,
        }
        channel = await bot.get_channel(channel_id=int(event.channel_id))
        base |= {
            "channel_id": str(event.channel_id),
            "channel_name": channel.name,
            "channel_type": CHANNEL_TYPE.get(channel.type, SceneType.CHANNEL_TEXT),
            "channel_avatar": channel.icon,
        }
        if isinstance(event.member, GuildMember):
            base |= {
                "nickname": event.member.nick or event.author.username,
                "role": await _handle_role(bot, str(event.guild_id), event.member.roles),
                "joined_at": event.member.joined_at,
            }
        else:
            member = await bot.get_guild_member(guild_id=event.guild_id, user_id=event.author.id)
            base |= {
                "nickname": member.nick or event.author.username,
                "role": await _handle_role(bot, str(event.guild_id), member.roles),
                "joined_at": member.joined_at,
            }
    return base


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        DirectMessageDeleteEvent,
        DirectMessageDeleteBulkEvent,
        GuildMessageDeleteEvent,
        GuildMessageDeleteBulkEvent,
        GuildMessageReactionRemoveAllEvent,
        DirectMessageReactionRemoveAllEvent,
        DirectMessageReactionRemoveEmojiEvent,
        GuildMessageReactionRemoveEmojiEvent,
    ],
):
    self_info = await bot.get_current_user()
    base = {
        "user_id": str(self_info.id),
        "name": self_info.username,
        "nickname": self_info.username,
        "avatar": self_info.avatar,
    }
    if isinstance(event.guild_id, Snowflake):
        guild = await bot.get_guild(guild_id=int(event.guild_id))
        base |= {
            "guild_id": str(event.guild_id),
            "guild_name": guild.name,
            "guild_avatar": guild.icon,
        }
        channel = await bot.get_channel(channel_id=int(event.channel_id))
        base |= {
            "channel_id": str(event.channel_id),
            "channel_name": channel.name,
            "channel_type": CHANNEL_TYPE.get(channel.type, SceneType.CHANNEL_TEXT),
            "channel_avatar": channel.icon,
        }
    return base


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        DirectMessageReactionAddEvent,
        DirectMessageReactionRemoveEvent,
        GuildMessageReactionAddEvent,
        GuildMessageReactionRemoveEvent,
    ],
):
    user = await bot.get_user(user_id=event.user_id)
    base = {
        "user_id": str(event.user_id),
        "name": user.username,
        "nickname": user.username,
        "avatar": user.avatar,
    }
    if isinstance(event.guild_id, Snowflake):
        guild = await bot.get_guild(guild_id=int(event.guild_id))
        base |= {
            "guild_id": str(event.guild_id),
            "guild_name": guild.name,
            "guild_avatar": guild.icon,
        }
        channel = await bot.get_channel(channel_id=int(event.channel_id))
        base |= {
            "channel_id": str(event.channel_id),
            "channel_name": channel.name,
            "channel_type": CHANNEL_TYPE.get(channel.type, SceneType.CHANNEL_TEXT),
            "channel_avatar": channel.icon,
        }
        member = await bot.get_guild_member(guild_id=event.guild_id, user_id=event.user_id)
        base |= {
            "nickname": member.nick or user.username,
            "role": await _handle_role(bot, str(event.guild_id), member.roles),
            "joined_at": member.joined_at,
        }
    return base


@fetcher.supply_wildcard
async def _(bot: Bot, event: Event):
    if isinstance(event, (ChannelCreateEvent, ChannelDeleteEvent, ChannelUpdateEvent)):
        self_info = await bot.get_current_user()
        base = {
            "user_id": str(self_info.id),
            "name": self_info.username,
            "nickname": self_info.username,
            "avatar": self_info.avatar,
        }
        base |= {
            "channel_id": str(event.id),
            "channel_name": event.name,
            "channel_type": CHANNEL_TYPE.get(event.type, SceneType.CHANNEL_TEXT),
            "channel_avatar": event.icon,
        }
        if isinstance(event.guild_id, Snowflake):
            guild = await bot.get_guild(guild_id=int(event.guild_id))
            base |= {
                "guild_id": str(event.guild_id),
                "guild_name": guild.name,
                "guild_avatar": guild.icon,
            }
        return base
    if isinstance(event, (GuildBanAddEvent, GuildBanRemoveEvent)):
        base = {
            "user_id": str(event.user.id),
            "name": event.user.username,
            "nickname": event.user.username,
            "avatar": event.user.avatar,
        }
        guild = await bot.get_guild(guild_id=int(event.guild_id))
        base |= {
            "guild_id": str(event.guild_id),
            "guild_name": guild.name,
            "guild_avatar": guild.icon,
        }
        return base
    if isinstance(event, (GuildCreateEvent, GuildUpdateEvent)):
        self_info = await bot.get_current_user()
        base = {
            "user_id": str(self_info.id),
            "name": self_info.username,
            "nickname": self_info.username,
            "avatar": self_info.avatar,
        }
        base |= {
            "guild_id": str(event.id),
            "guild_name": event.name,
            "guild_avatar": event.icon,
        }
        return base
    if isinstance(event, GuildDeleteEvent):
        self_info = await bot.get_current_user()
        base = {
            "user_id": str(self_info.id),
            "name": self_info.username,
            "nickname": self_info.username,
            "avatar": self_info.avatar,
            "guild_id": str(event.id),
            "guild_name": "",
            "guild_avatar": "",
        }
        return base
    if isinstance(event, GuildMemberAddEvent):
        base = {
            "user_id": str(event.user.id),
            "name": event.user.username,
            "nickname": event.nick or "",
            "avatar": event.avatar or event.user.avatar,
            "role": await _handle_role(bot, str(event.guild_id), event.roles),
            "joined_at": event.joined_at,
        }
        guild = await bot.get_guild(guild_id=int(event.guild_id))
        base |= {
            "guild_id": str(event.guild_id),
            "guild_name": guild.name,
            "guild_avatar": guild.icon,
        }
        return base
    if isinstance(event, GuildMemberUpdateEvent):
        base = {
            "user_id": str(event.user.id),
            "name": event.user.username,
            "nickname": event.nick or "",
            "avatar": event.user.avatar,
            "role": await _handle_role(bot, str(event.guild_id), event.roles),
            "joined_at": event.joined_at,
        }
        guild = await bot.get_guild(guild_id=int(event.guild_id))
        base |= {
            "guild_id": str(event.guild_id),
            "guild_name": guild.name,
            "guild_avatar": guild.icon,
        }
        return base
    if isinstance(event, GuildMemberRemoveEvent):
        base = {
            "user_id": str(event.user.id),
            "name": event.user.username,
            "nickname": event.user.username,
            "avatar": event.user.avatar,
        }
        guild = await bot.get_guild(guild_id=int(event.guild_id))
        base |= {
            "guild_id": str(event.guild_id),
            "guild_name": guild.name,
            "guild_avatar": guild.icon,
        }
        return base
    raise NotImplementedError
