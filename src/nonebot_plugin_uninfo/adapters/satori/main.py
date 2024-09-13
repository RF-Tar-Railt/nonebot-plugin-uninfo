from typing import Optional

from nonebot.adapters.satori import Bot
from nonebot.adapters.satori.event import Event
from nonebot.adapters.satori.models import ChannelType

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Role, Scene, SceneType, User

ROLES = {
    "OWNER": 100,
    "ADMINISTRATOR": 10,
    "MEMBER": 1,
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            nick=data["nickname"],
            avatar=data.get("avatar"),
        )

    def extract_scene(self, data):
        if "scene_id" in data:
            if "parent_id" in data:
                return Scene(
                    id=data["scene_id"],
                    type=data["scene_type"],
                    name=data["scene_name"],
                    parent=Scene(
                        id=data["parent_id"],
                        type=data["parent_type"],
                        name=data.get("parent_name"),
                        avatar=data.get("parent_avatar"),
                    ),
                )
            return Scene(
                id=data["scene_id"],
                type=data["scene_type"],
                name=data["scene_name"],
                avatar=data.get("scene_avatar"),
            )
        return Scene(
            id=data["user_id"],
            type=SceneType.PRIVATE,
            avatar=data.get("avatar"),
        )

    def extract_member(self, data, user: Optional[User]):
        if "scene_id" not in data:
            return None
        if user:
            return Member(
                user=user,
                nick=data["member_name"],
                role=(
                    Role(data["role_id"], ROLES.get(data["role_name"], 1), data["role_name"])
                    if "role_id" in data
                    else None
                ),
                joined_at=data["joined_at"],
            )
        return Member(
            User(
                id=data["user_id"],
                name=data["name"],
                nick=data.get("nickname"),
                avatar=data.get("avatar"),
            ),
            nick=data["member_name"],
            role=(
                Role(data["role_id"], ROLES.get(data["role_name"], 1), data["role_name"]) if "role_id" in data else None
            ),
            joined_at=data["joined_at"],
        )

    def _pack_user(self, user):
        data = {
            "user_id": user.id,
            "name": user.name,
            "nickname": user.nick,
            "avatar": user.avatar,
        }
        return self.extract_user(data)

    async def query_user(self, bot: Bot):
        friends = await bot.friend_list()
        for friend in friends.data:
            yield self._pack_user(friend)
        while friends.next:
            friends = await bot.friend_list(next_token=friends.next)
            for friend in friends.data:
                yield self._pack_user(friend)

    def _pack_guild(self, bot: Bot, guild):
        data = {
            "scene_id": guild.id,
            "scene_type": SceneType.GROUP if "guild.plain" in bot._self_info.features else SceneType.GUILD,
            "scene_name": guild.name,
            "scene_avatar": guild.avatar,
        }
        return self.extract_scene(data)

    def _pack_channel(self, bot: Bot, guild, channel):
        data = {
            "scene_id": channel.id,
            "scene_type": SceneType.GROUP if "guild.plain" else TYPE_MAPPING[channel.type],
            "scene_name": channel.name,
            "parent_id": guild.id,
            "parent_type": SceneType.GROUP if "guild.plain" in bot._self_info.features else SceneType.GUILD,
            "parent_name": guild.name,
            "parent_avatar": guild.avatar,
        }
        return self.extract_scene(data)

    async def query_scene(self, bot: Bot, guild_id: Optional[str]):
        guilds = await bot.guild_list()
        for guild in guilds.data:
            if not guild_id or guild.id == guild_id:
                yield self._pack_guild(bot, guild)
                channels = await bot.channel_list(guild_id=guild.id)
                for channel in channels.data:
                    yield self._pack_channel(bot, guild, channel)
                while channels.next:
                    channels = await bot.channel_list(guild_id=guild.id, next_token=channels.next)
                    for channel in channels.data:
                        yield self._pack_channel(bot, guild, channel)
        while guilds.next:
            guilds = await bot.guild_list(next_token=guilds.next)
            for guild in guilds.data:
                if not guild_id or guild.id == guild_id:
                    yield self._pack_guild(bot, guild)
                    channels = await bot.channel_list(guild_id=guild.id)
                    for channel in channels.data:
                        yield self._pack_channel(bot, guild, channel)
                    while channels.next:
                        channels = await bot.channel_list(guild_id=guild.id, next_token=channels.next)
                        for channel in channels.data:
                            yield self._pack_channel(bot, guild, channel)

    async def query_member(self, bot: Bot, guild_id: str):
        members = await bot.guild_member_list(guild_id=guild_id)
        for member in members.data:
            if not member.user:
                continue
            data = {
                "scene_id": guild_id,
                "user_id": member.user.id,
                "name": member.user.name,
                "nickname": member.user.nick,
                "member_name": member.nick,
                "joined_at": member.joined_at,
            }
            yield self.extract_member(data, None)


fetcher = InfoFetcher(SupportAdapter.satori)


TYPE_MAPPING = {
    ChannelType.DIRECT: SceneType.PRIVATE,
    ChannelType.TEXT: SceneType.CHANNEL_TEXT,
    ChannelType.VOICE: SceneType.CHANNEL_VOICE,
    ChannelType.CATEGORY: SceneType.CHANNEL_CATEGORY,
}


@fetcher.supply_wildcard
async def _(bot: Bot, event: Event):
    if not event.user:
        user_id = event.self_id
        name = ""
        nickname = ""
    else:
        user_id = event.user.id
        name = event.user.name
        nickname = event.user.nick
    base = {
        "self_id": str(bot.self_id),
        "adapter": SupportAdapter.satori,
        "scope": SupportScope.ensure_satori(bot.platform),
        "user_id": user_id,
        "name": name,
        "nickname": nickname,
    }
    if event.user:
        base["avatar"] = event.user.avatar
    if event.guild and event.channel:
        base["scene_id"] = event.channel.id
        base["scene_type"] = TYPE_MAPPING[event.channel.type]
        if event.channel.type == ChannelType.DIRECT:
            del base["scene_id"]
            return base
        base["scene_name"] = event.channel.name
        base["parent_id"] = event.guild.id
        base["parent_type"] = SceneType.GUILD
        base["parent_name"] = event.guild.name
        base["parent_avatar"] = event.guild.avatar
        if "guild.plain" in bot._self_info.features or event.guild.id == event.channel.id:
            base["scene_type"] = SceneType.GROUP
            base["parent_type"] = SceneType.GROUP
    elif event.guild:
        base["scene_id"] = event.guild.id
        base["scene_type"] = SceneType.GROUP if "guild.plain" in bot._self_info.features else SceneType.GUILD
        base["scene_name"] = event.guild.name
        base["scene_avatar"] = event.guild.avatar
    elif event.channel:
        base["scene_id"] = event.channel.id
        base["scene_type"] = SceneType.GROUP if "guild.plain" else TYPE_MAPPING[event.channel.type]
        if event.channel.type == ChannelType.DIRECT:
            del base["scene_id"]
            return base
        base["scene_name"] = event.channel.name
    if event.member:
        base["member_name"] = event.member.nick
        base["joined_at"] = event.member.joined_at
        if event.member.avatar:
            base["avatar"] = event.member.avatar
    if event.role:
        base["role_id"] = event.role.id
        base["role_name"] = event.role.name
    if event.operator:
        base["operator"] = {
            "user_id": event.operator.id,
            "name": event.operator.name,
            "nickname": event.operator.nick,
            "member_name": event.operator.nick,
            "avatar": event.operator.avatar,
            "joined_at": None,
        }
    return base