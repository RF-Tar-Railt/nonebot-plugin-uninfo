from datetime import datetime, timedelta
from typing import Optional

from nonebot.adapters.kaiheila import Bot
from nonebot.adapters.kaiheila.api.model import Channel as KookChannel
from nonebot.adapters.kaiheila.event import Event, HeartbeatMetaEvent, LifecycleMetaEvent

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, MuteInfo, Role, Scene, SceneType, User


async def _handle_role(bot: Bot, guild_id: str, roles: list[int]):
    if not roles:
        return Role("MEMBER", 1, "member")
    res = []
    resp = await bot.guildRole_list(guild_id=guild_id)
    if not resp.roles:
        return Role("MEMBER", 1, "member")
    for role in resp.roles:
        if role.role_id not in roles:
            continue
        perm = int(role.permissions)  # type: ignore
        if perm & (1 << 0) == (1 << 0):
            if perm & (1 << 1) == (1 << 1):
                res.append(("OWNER", 100, role.name))
            res.append(("ADMINISTRATOR", 10, role.name))
        if perm & (1 << 5) == (1 << 5):
            res.append(("CHANNEL_ADMINISTRATOR", 9, role.name))
        res.append((str(role.role_id), 1, role.name))
    if not res:
        return Role("MEMBER", 1, "member")
    return Role(*sorted(res, key=lambda x: x[1], reverse=True)[0])


def _handle_channel_type(channel: KookChannel):
    if channel.is_category:
        return SceneType.CHANNEL_CATEGORY
    if channel.type == 2:
        return SceneType.CHANNEL_VOICE
    return SceneType.CHANNEL_TEXT


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            avatar=data["avatar"],
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
                ),
                nick=data["nickname"],
                role=data.get("role"),
                joined_at=data.get("joined_at"),
            )
        return None

    async def query_user(self, bot: Bot, user_id: str):
        raise NotImplementedError

    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type == SceneType.GUILD:
            guild = await bot.guild_view(guild_id=scene_id)
            return self.extract_scene(
                {
                    "guild_id": guild.id_,
                    "guild_name": guild.name,
                    "guild_avatar": guild.icon,
                }
            )

        elif scene_type >= SceneType.CHANNEL_TEXT:
            channel = await bot.channel_view(target_id=scene_id)
            return self.extract_scene(
                {
                    "channel_id": channel.id_,
                    "channel_name": channel.name,
                    "channel_type": _handle_channel_type(channel),
                }
            )

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        if scene_type != SceneType.GUILD:
            return
        guild_id = parent_scene_id

        member = await bot.user_view(guild_id=guild_id, user_id=user_id)
        user = User(
            id=str(member.id_),
            name=member.username,
            avatar=member.avatar,
        )
        return Member(
            user=user,
            nick=member.nickname or member.username,
            role=await _handle_role(bot, guild_id, member.roles or []),
            joined_at=datetime.fromtimestamp(member.joined_at / 1000) if member.joined_at else None,
            mute=MuteInfo(muted=True, duration=timedelta(60)) if member.status == 10 else None,
        )

    async def query_users(self, bot: Bot):
        while True:
            resp = await bot.userChat_list()
            for chat in resp.user_chats or []:
                if chat.target_info:
                    yield User(
                        id=chat.target_info.id_ or "",
                        name=chat.target_info.username,
                        avatar=chat.target_info.avatar,
                    )
            if not resp.meta or resp.meta.page == resp.meta.page_total:
                break
            resp = await bot.userChat_list(page=(resp.meta.page or 0) + 1)

    async def query_scenes(
        self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type == SceneType.GROUP:
            return

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

        while True:
            resp = await bot.guild_list()
            for guild in resp.guilds or []:
                if not guild.id_:
                    continue
                if parent_scene_id is None or str(guild.id_) == parent_scene_id:
                    _guild = Scene(
                        id=str(guild.id_),
                        type=SceneType.GUILD,
                        name=guild.name,
                        avatar=guild.icon,
                    )
                    if scene_type is None or scene_type == SceneType.GUILD:
                        yield _guild
                    if scene_type == SceneType.GUILD:
                        continue
                    channels = guild.channels or (await bot.channel_list(guild_id=guild.id_)).channels or []
                    for channel in channels:
                        yield Scene(
                            id=str(channel.id_),
                            type=_handle_channel_type(channel),
                            name=channel.name,
                            parent=_guild,
                        )
            if not resp.meta or resp.meta.page == resp.meta.page_total:
                break
            resp = await bot.guild_list(page=(resp.meta.page or 0) + 1)

    async def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        if scene_type != SceneType.GUILD:
            return
        guild_id = parent_scene_id

        while True:
            resp = await bot.guild_userList(guild_id=guild_id)
            for member in resp.users or []:
                user = User(
                    id=str(member.id_),
                    name=member.username,
                    avatar=member.avatar,
                )
                yield Member(
                    user=user,
                    nick=member.nickname or member.username,
                    role=await _handle_role(bot, guild_id, member.roles or []),
                    joined_at=datetime.fromtimestamp(member.joined_at / 1000) if member.joined_at else None,
                    mute=MuteInfo(muted=True, duration=timedelta(60)) if member.status == 10 else None,
                )

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.kook,
            "scope": SupportScope.kook,
        }


fetcher = InfoFetcher(SupportAdapter.kook)


@fetcher.supply
async def _(bot: Bot, event: LifecycleMetaEvent):
    raise NotImplementedError


@fetcher.supply
async def _(bot: Bot, event: HeartbeatMetaEvent):
    raise NotImplementedError


@fetcher.supply_wildcard
async def _(bot: Bot, event: Event):
    user = event.extra.author or await bot.user_view(user_id=event.user_id)
    base = {
        "user_id": user.id_,
        "name": user.username,
        "nickname": user.nickname,
        "avatar": user.avatar,
    }
    if event.channel_type == "PERSON":
        return base
    if event.type_ != 255:
        channel = await bot.channel_view(target_id=event.target_id)
        base |= {
            "channel_id": channel.id_,
            "channel_name": channel.name or event.extra.channel_name,
            "channel_type": _handle_channel_type(channel),
        }
        if channel.guild_id or event.extra.guild_id:
            guild_id = channel.guild_id or event.extra.guild_id or ""
            guild = await bot.guild_view(guild_id=guild_id)
            base |= {
                "guild_id": guild.id_,
                "guild_name": guild.name,
                "guild_avatar": guild.icon,
            }
            member = await bot.user_view(guild_id=guild_id, user_id=event.user_id)
            base |= {
                "nickname": member.nickname,
                "role": await _handle_role(bot, guild_id, member.roles or []),
                "joined_at": datetime.fromtimestamp(member.joined_at / 1000) if member.joined_at else None,
            }
    else:
        guild_id = event.extra.guild_id or event.target_id
        guild = await bot.guild_view(guild_id=guild_id)
        base |= {
            "guild_id": guild.id_,
            "guild_name": guild.name,
            "guild_avatar": guild.icon,
        }
        member = await bot.user_view(guild_id=guild_id, user_id=event.user_id)
        base |= {
            "nickname": member.nickname,
            "role": await _handle_role(bot, guild_id, member.roles or []),
            "joined_at": datetime.fromtimestamp(member.joined_at / 1000) if member.joined_at else None,
        }
    return base
