from typing import Optional, Union

from nonebot.adapters.dodo import Bot
from nonebot.adapters.dodo.event import (
    CardMessageButtonClickEvent,
    CardMessageFormSubmitEvent,
    CardMessageListSubmitEvent,
    ChannelArticleCommentEvent,
    ChannelArticleEvent,
    ChannelMessageEvent,
    ChannelVoiceMemberJoinEvent,
    ChannelVoiceMemberLeaveEvent,
    MessageReactionEvent,
    PersonalMessageEvent,
)
from nonebot.adapters.dodo.models import ChannelType

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.fetch import SuppliedData
from nonebot_plugin_uninfo.model import Member, Role, Scene, SceneType, User


async def _handle_role(bot: Bot, guild_id: str, user_id: str):
    res = []
    resp = await bot.get_member_role_list(island_source_id=guild_id, dodo_source_id=user_id)
    for role in resp:
        perm = int(role.permission)  # type: ignore
        if perm & (1 << 0) == (1 << 0):
            if perm & (1 << 1) == (1 << 1):
                res.append(("OWNER", 100, role.role_name))
            res.append(("ADMINISTRATOR", 10, role.role_name))
        if perm & (1 << 5) == (1 << 5):
            res.append(("CHANNEL_ADMINISTRATOR", 9, role.role_name))
        res.append((str(role.role_id), 1, role.role_name))
    if not res:
        return Role("MEMBER", 1, "member")
    return Role(*sorted(res, key=lambda x: x[1], reverse=True)[0])


CHANNEL_TYPE = {
    ChannelType.TEXT: SceneType.CHANNEL_TEXT,
    ChannelType.VOICE: SceneType.CHANNEL_VOICE,
    ChannelType.ARTICLE: SceneType.CHANNEL_TEXT,
    ChannelType.LINK: SceneType.CHANNEL_CATEGORY,
    ChannelType.PROFILE: SceneType.CHANNEL_CATEGORY,
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            avatar=data["avatar"],
            gender=data["gender"],
        )

    def extract_scene(self, data):
        if "guild_id" in data:
            if "channel_id" in data:
                return Scene(
                    id=data["channel_id"],
                    name=data.get("channel_name"),
                    type=data.get("channel_type", SceneType.CHANNEL_TEXT),
                    parent=Scene(
                        id=data["guild_id"],
                        name=data.get("guild_name"),
                        type=SceneType.GUILD,
                        avatar=data.get("guild_avatar"),
                    ),
                )
            return Scene(
                id=data["guild_id"],
                name=data.get("guild_name"),
                type=SceneType.GUILD,
                avatar=data.get("guild_avatar"),
            )
        if "channel_id" in data:
            return Scene(
                id=data["channel_id"],
                name=data.get("channel_name"),
                type=data.get("channel_type", SceneType.CHANNEL_TEXT),
            )
        return Scene(
            id=data["user_id"],
            type=SceneType.PRIVATE,
            name=data["name"],
            avatar=data["avatar"],
        )

    def extract_member(self, data, user: Optional[User]):
        if "guild_id" in data or "channel_id" in data:
            if user:
                return Member(user, nick=data["nickname"], role=data.get("role"), joined_at=data.get("joined_at"))
            return Member(
                User(
                    id=data["user_id"],
                    name=data["name"],
                    avatar=data.get("avatar"),
                    gender=data["gender"],
                ),
                nick=data["nickname"],
                role=data.get("role"),
                joined_at=data.get("joined_at"),
            )
        return None

    async def query_user(self, bot: Bot):
        raise NotImplementedError

    async def query_scene(self, bot: Bot, guild_id: Optional[str]):
        guilds = await bot.get_island_list()
        for guild in guilds:
            if not guild_id or guild_id == guild.island_source_id:
                _guild = Scene(
                    id=guild.island_source_id,
                    type=SceneType.GUILD,
                    name=guild.island_name,
                    avatar=guild.cover_url,
                )
                yield _guild
                channels = await bot.get_channel_list(island_source_id=guild.island_source_id)
                for channel in channels:
                    yield Scene(
                        id=channel.channel_id,
                        type=CHANNEL_TYPE.get(channel.channel_type, SceneType.CHANNEL_TEXT),
                        name=channel.channel_name,
                        parent=_guild,
                    )

    async def query_member(self, bot: Bot, guild_id: str):
        members = await bot.get_member_list(island_source_id=guild_id, page_size=100)
        while members.list:
            for member in members.list:
                user = User(
                    id=member.dodo_source_id,
                    name=member.personal_nick_name,
                    avatar=member.avatar_url,
                    gender="male" if member.sex == 1 else "female" if member.sex == 0 else "unknown",
                )
                yield Member(
                    user=user,
                    nick=member.nick_name,
                    role=await _handle_role(bot, guild_id, member.dodo_source_id),
                    joined_at=member.join_time,
                )
            if len(members.list) < 100:
                break
            members = await bot.get_member_list(island_source_id=guild_id, page_size=100, max_id=members.max_id)

    def supply_self(self, bot: Bot) -> SuppliedData:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.dodo,
            "scope": SupportScope.dodo,
        }


fetcher = InfoFetcher(SupportAdapter.dodo)


@fetcher.supply
async def _(bot: Bot, event: PersonalMessageEvent):
    return {
        "user_id": event.dodo_source_id,
        "name": event.personal.nick_name,
        "avatar": event.personal.avatar_url,
        "gender": "male" if event.personal.sex == 1 else "female" if event.personal.sex == 0 else "unknown",
    }


@fetcher.supply
async def _(
    bot: Bot,
    event: Union[
        ChannelMessageEvent,
        MessageReactionEvent,
        CardMessageButtonClickEvent,
        CardMessageFormSubmitEvent,
        CardMessageListSubmitEvent,
        ChannelVoiceMemberJoinEvent,
        ChannelVoiceMemberLeaveEvent,
        ChannelArticleEvent,
        ChannelArticleCommentEvent,
    ],
):
    base = {
        "user_id": event.dodo_source_id,
        "name": event.personal.nick_name,
        "avatar": event.personal.avatar_url,
        "gender": "male" if event.personal.sex == 1 else "female" if event.personal.sex == 0 else "unknown",
    }
    guild = await bot.get_island_info(island_source_id=event.island_source_id)
    base |= {
        "guild_id": event.island_source_id,
        "guild_name": guild.island_name,
        "guild_avatar": guild.cover_url,
    }
    channel = await bot.get_channel_info(channel_id=event.channel_id)
    base |= {
        "channel_id": event.channel_id,
        "channel_name": channel.channel_name,
        "channel_type": CHANNEL_TYPE.get(channel.channel_type, SceneType.CHANNEL_TEXT),
    }
    base |= {
        "nickname": event.member.nick_name,
        "role": await _handle_role(bot, event.island_source_id, event.dodo_source_id),
        "joined_at": event.member.join_time,
    }
    return base
