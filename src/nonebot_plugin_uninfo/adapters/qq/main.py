from typing import Optional, Union

from nonebot.adapters.qq import Bot
from nonebot.adapters.qq.event import (
    C2CMessageCreateEvent,
    ChannelEvent,
    Event,
    GroupAtMessageCreateEvent,
    GuildEvent,
    GuildMemberEvent,
    GuildMessageEvent,
    InteractionCreateEvent,
    MessageDeleteEvent,
)
from nonebot.exception import ActionFailed

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Role, Scene, SceneType, User

ROLES = {
    "4": ("OWNER", 100, "创建者"),
    "2": ("ADMINISTRATOR", 10, "管理员"),
    "5": ("CHANNEL_ADMINISTRATOR", 8, "子频道管理员"),
    "1": ("MEMBER", 1, "成员"),
}


CHANNEL_TYPE = {
    0: SceneType.CHANNEL_TEXT,
    2: SceneType.CHANNEL_VOICE,
    4: SceneType.CHANNEL_CATEGORY,
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            avatar=data["avatar"],
        )

    def extract_scene(self, data):
        if "group_id" in data:
            return Scene(
                id=data["group_id"],
                type=SceneType.GROUP,
            )
        if "guild_id" in data:
            if "channel_id" in data:
                return Scene(
                    id=data["channel_id"],
                    name=data.get("channel_name"),
                    type=CHANNEL_TYPE.get(data.get("channel_type", 0), SceneType.CHANNEL_TEXT),
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
        return Scene(
            id=data["user_id"],
            type=SceneType.PRIVATE,
            name=data["name"],
            avatar=data["avatar"],
        )

    def extract_member(self, data, user: Optional[User]):
        if "group_id" in data:
            if user:
                return Member(user, nick=data["nickname"])
            return Member(
                User(
                    id=data["user_id"],
                    name=data["name"],
                    avatar=data.get("avatar"),
                ),
                nick=data["nickname"],
            )
        if "guild_id" in data:
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
            guild = await bot.get_guild(guild_id=scene_id)
            return Scene(id=guild.id, type=SceneType.GUILD, name=guild.name, avatar=guild.icon)

        elif scene_type >= SceneType.CHANNEL_TEXT:
            channel = await bot.get_channel(channel_id=scene_id)
            guild = await bot.get_guild(guild_id=channel.guild_id)
            return Scene(
                id=channel.id,
                type=CHANNEL_TYPE.get(channel.type, SceneType.CHANNEL_TEXT),
                name=channel.name,
                parent=Scene(id=guild.id, type=SceneType.GUILD, name=guild.name, avatar=guild.icon),
            )

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        if scene_type == SceneType.GUILD:
            member = await bot.get_member(guild_id=parent_scene_id, user_id=user_id)
            return Member(
                User(
                    id=member.user.id if member.user else user_id,
                    name=(member.user.username if member.user else "") or "",
                    avatar=member.user.avatar if member.user else None,
                ),
                nick=member.nick,
                role=await _handle_role(bot, parent_scene_id, None, member.roles or []),
                joined_at=member.joined_at,
            )

    def query_users(self, bot: Bot):
        raise NotImplementedError

    async def query_scenes(
        self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type is not None and scene_type < SceneType.GUILD:
            return

        guilds = await bot.guilds(limit=100)
        while guilds:
            for guild in guilds:
                if parent_scene_id is None or guild.id == parent_scene_id:
                    _guild = Scene(id=guild.id, type=SceneType.GUILD, name=guild.name, avatar=guild.icon)
                    if scene_type is None or scene_type == SceneType.GUILD:
                        yield _guild
                    if scene_type == SceneType.GUILD:
                        continue
                    channels = await bot.get_channels(guild_id=guild.id)
                    for channel in channels:
                        yield Scene(
                            id=channel.id,
                            type=CHANNEL_TYPE.get(channel.type, SceneType.CHANNEL_TEXT),
                            name=channel.name,
                            parent=_guild,
                        )
            if len(guilds) < 100:
                break
            guilds = await bot.guilds(limit=100, after=guilds[-1].id)

    def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        raise NotImplementedError

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.qq,
            "scope": SupportScope.qq_api,
        }


fetcher = InfoFetcher(SupportAdapter.qq)


async def _handle_role(bot: Bot, guild_id: str, channel_id: Union[str, None], roles: list[str]):
    if not roles:
        return Role(*ROLES["1"])
    res = []
    try:
        resp = await bot.get_guild_roles(guild_id=guild_id)
        roles_info = {r.id: r.name for r in resp.roles}
    except ActionFailed:
        roles_info = {}
    for role in roles:
        if role in ROLES:
            res.append(ROLES[role])
            continue
        if not channel_id:
            res.append(("MEMBER", 1, roles_info.get(role, "成员")))
            continue
        try:
            perm = await bot.get_channel_roles_permissions(channel_id=channel_id, role_id=role)
            if perm.permissions & 0b10 == 0b10:
                res.append(("MEMBER", perm.permissions, roles_info.get(role, "成员")))
            else:
                res.append(("CHANNEL_ADMINISTRATOR", perm.permissions, roles_info.get(role, "子频道管理员")))
        except ActionFailed:
            res.append(("MEMBER", 1, roles_info.get(role, "成员")))
    if not res:
        return Role(*ROLES["1"])
    return Role(*sorted(res, key=lambda x: x[1], reverse=True)[0])


@fetcher.supply
async def _(bot: Bot, event: InteractionCreateEvent):
    if event.chat_type == 2:
        return {
            "user_id": event.user_openid,
            "name": "",
            "nickname": "",
            "avatar": f"https://q.qlogo.cn/qqapp/{bot.bot_info.id}/{event.user_openid}/100",
        }
    if event.chat_type == 1:
        return {
            "user_id": event.group_member_openid,
            "name": "",
            "nickname": "",
            "avatar": f"https://q.qlogo.cn/qqapp/{bot.bot_info.id}/{event.group_member_openid}/100",
            "group_id": event.group_openid,
        }
    base = {
        "user_id": event.data.resolved.user_id,
        "name": "",
        "nickname": "",
        "avatar": None,
        "guild_id": event.guild_id,
        "channel_id": event.channel_id,
    }
    try:
        member = await bot.get_member(guild_id=event.guild_id, user_id=event.data.resolved.user_id)  # type: ignore
        base["name"] = (member.user.username if member.user else "") or ""
        base["nickname"] = member.nick or ""
        base["role"] = await _handle_role(bot, event.guild_id, event.channel_id, member.roles or [])  # type: ignore
        base["joined_at"] = member.joined_at
    except ActionFailed:
        pass
    try:
        guild = await bot.get_guild(guild_id=event.guild_id)  # type: ignore
        base["guild_name"] = guild.name
        base["guild_avatar"] = guild.icon
        channel = await bot.get_channel(channel_id=event.channel_id)  # type: ignore
        base["channel_name"] = channel.name
        base["channel_type"] = channel.type
    except ActionFailed:
        pass
    return base


@fetcher.supply
async def _(bot: Bot, event: C2CMessageCreateEvent):
    return {
        "user_id": event.author.user_openid,
        "name": "",
        "nickname": "",
        "avatar": f"https://q.qlogo.cn/qqapp/{bot.bot_info.id}/{event.author.user_openid}/100",
    }


@fetcher.supply
async def _(bot: Bot, event: GroupAtMessageCreateEvent):
    return {
        "user_id": event.author.member_openid,
        "name": "",
        "nickname": "",
        "avatar": f"https://q.qlogo.cn/qqapp/{bot.bot_info.id}/{event.author.member_openid}/100",
        "group_id": event.group_openid,
    }


@fetcher.supply_wildcard
async def _(bot: Bot, event: Event):
    if isinstance(event, GuildMessageEvent):
        base = {
            "user_id": event.author.id,
            "name": event.author.username or "",
            "nickname": "",
            "avatar": event.author.avatar,
            "guild_id": event.guild_id,
            "channel_id": event.channel_id,
        }
        if event.member:
            base |= {
                "nickname": event.member.nick or "",
                "role": await _handle_role(bot, event.guild_id, event.channel_id, event.member.roles or []),
                "joined_at": event.member.joined_at,
            }
        try:
            guild = await bot.get_guild(guild_id=event.guild_id)
            base["guild_name"] = guild.name
            base["guild_avatar"] = guild.icon
            channel = await bot.get_channel(channel_id=event.channel_id)
            base["channel_name"] = channel.name
            base["channel_type"] = channel.type
        except ActionFailed:
            pass
        return base
    if isinstance(event, MessageDeleteEvent):
        message_event = event.message
        base = {
            "user_id": message_event.author.id,
            "name": message_event.author.username or "",
            "nickname": "",
            "avatar": message_event.author.avatar,
            "guild_id": message_event.guild_id,
            "channel_id": message_event.channel_id,
        }
        if message_event.member:
            base |= {
                "nickname": message_event.member.nick or "",
                "role": await _handle_role(
                    bot, message_event.guild_id, message_event.channel_id, message_event.member.roles or []
                ),
                "joined_at": message_event.member.joined_at,
            }
        try:
            guild = await bot.get_guild(guild_id=message_event.guild_id)
            base["guild_name"] = guild.name
            base["guild_avatar"] = guild.icon
            channel = await bot.get_channel(channel_id=message_event.channel_id)
            base["channel_name"] = channel.name
            base["channel_type"] = channel.type
        except ActionFailed:
            pass
        base["operator"] = {
            "user_id": event.op_user.id,
            "name": event.op_user.username or "",
            "nickname": "",
            "avatar": event.op_user.avatar,
        }
        try:
            operator = await bot.get_member(guild_id=message_event.guild_id, user_id=event.op_user.id)
            base["operator"] |= {
                "nickname": operator.nick or "",
                "role": await _handle_role(bot, message_event.guild_id, message_event.channel_id, operator.roles or []),
                "joined_at": operator.joined_at,
            }
        except ActionFailed:
            pass
        return base
    if isinstance(event, GuildEvent):
        me = bot.self_info
        base = {
            "user_id": me.id,
            "name": me.username or "",
            "nickname": "",
            "avatar": me.avatar,
            "guild_id": event.id,
            "guild_name": event.name,
            "guild_avatar": event.icon,
        }
        try:
            operator = await bot.get_member(guild_id=event.id, user_id=event.op_user_id)
            base["operator"] = {
                "user_id": event.op_user_id,
                "name": (operator.user.username if operator.user else "") or "",
                "nickname": operator.nick or "",
                "avatar": operator.user.avatar if operator.user else None,
                "role": await _handle_role(bot, event.id, None, operator.roles or []),
                "joined_at": operator.joined_at,
            }
        except ActionFailed:
            pass
        return base
    if isinstance(event, GuildMemberEvent):
        base = {
            "user_id": event.user.id,  # type: ignore
            "name": (event.user.username if event.user else "") or "",
            "nickname": event.nick or "",
            "avatar": event.user.avatar if event.user else None,
            "guild_id": event.guild_id,
            "role": await _handle_role(bot, event.guild_id, None, event.roles or []),
            "joined_at": event.joined_at,
        }
        try:
            guild = await bot.get_guild(guild_id=event.guild_id)
            base["guild_name"] = guild.name
            base["guild_avatar"] = guild.icon
        except ActionFailed:
            pass
        try:
            operator = await bot.get_member(guild_id=event.guild_id, user_id=event.op_user_id)
            base["operator"] = {
                "user_id": event.op_user_id,
                "name": (operator.user.username if operator.user else "") or "",
                "nickname": operator.nick or "",
                "avatar": operator.user.avatar if operator.user else None,
                "role": await _handle_role(bot, event.guild_id, None, operator.roles or []),
                "joined_at": operator.joined_at,
            }
        except ActionFailed:
            pass
        return base
    if isinstance(event, ChannelEvent):
        me = bot.self_info
        base = {
            "user_id": me.id,
            "name": me.username or "",
            "nickname": "",
            "avatar": me.avatar,
            "guild_id": event.guild_id,
            "channel_id": event.id,
            "channel_name": event.name,
            "channel_type": event.type,
        }
        try:
            guild = await bot.get_guild(guild_id=event.guild_id)
            base["guild_name"] = guild.name
            base["guild_avatar"] = guild.icon
        except ActionFailed:
            pass
        try:
            operator = await bot.get_member(guild_id=event.guild_id, user_id=event.op_user_id)
            base["operator"] = {
                "user_id": event.op_user_id,
                "name": (operator.user.username if operator.user else "") or "",
                "nickname": operator.nick or "",
                "avatar": operator.user.avatar if operator.user else None,
                "role": await _handle_role(bot, event.guild_id, event.id, operator.roles or []),
                "joined_at": operator.joined_at,
            }
        except ActionFailed:
            pass
        return base
    raise NotImplementedError
