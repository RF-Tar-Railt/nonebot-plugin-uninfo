from typing import Optional

from nonebot.adapters.console import Bot
from nonebot.adapters.console.event import Event
from nonechat.model import DIRECT

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Scene, SceneType, User


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(data['avatar']):x}.png",
        )

    def extract_scene(self, data):
        if "channel_id" in data:
            return Scene(
                id=data["channel_id"],
                type=SceneType.GROUP,
                name=data["channel_name"],
                avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(data['channel_avatar']):x}.png",
            )
        return Scene(
            id=f"private:{data['user_id']}",
            type=SceneType.PRIVATE,
            name=data["name"],
            avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(data['avatar']):x}.png",
        )

    def extract_member(self, data, user: Optional[User]):
        if user is None:
            user = self.extract_user(data)
        return Member(user, user.name)

    async def query_user(self, bot: Bot, user_id: str):
        try:
            user = await bot.get_user(user_id)
            return User(
                user.id,
                user.nickname,
                avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(user.avatar):x}.png",
            )
        except Exception:
            return User(user_id)

    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type == SceneType.PRIVATE:
            if user := await self.query_user(bot, scene_id):
                return Scene(id=f"private:{user.id}", type=SceneType.PRIVATE, name=user.name, avatar=user.avatar)
        if scene_type == SceneType.GROUP:
            try:
                channel = await bot.get_channel(scene_id)
                return Scene(
                    id=channel.id,
                    type=SceneType.GROUP,
                    name=channel.name,
                    avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(channel.avatar):x}.png",
                )
            except Exception:
                return Scene(id=scene_id, type=SceneType.GROUP)

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        return Member(await self.query_user(bot, user_id))

    async def query_users(self, bot: Bot):
        for user in await bot.list_users():
            yield User(
                user.id,
                user.nickname,
                avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(user.avatar):x}.png",
            )

    async def query_scenes(
        self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type is None or scene_type == SceneType.PRIVATE:
            for user in await bot.list_users():
                yield Scene(
                    id=f"private:{user.id}",
                    type=SceneType.PRIVATE,
                    name=user.nickname,
                    avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(user.avatar):x}.png",
                )
        if scene_type is None or scene_type == SceneType.GROUP:
            for channel in await bot.list_channels():
                yield Scene(
                    id=channel.id,
                    type=SceneType.GROUP,
                    name=channel.name,
                    avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(channel.avatar):x}.png",
                )

    async def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        for user in await bot.list_users():
            yield Member(
                user=User(
                    user.id,
                    user.nickname,
                    avatar=f"https://emoji.aranja.com/static/emoji-data/img-apple-160/{ord(user.avatar):x}.png",
                ),
                nick=user.nickname,
            )

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.console,
            "scope": SupportScope.console,
        }


fetcher = InfoFetcher(SupportAdapter.console)


@fetcher.supply_wildcard
async def _(bot: Bot, event: Event):
    base = {"user_id": event.user.id, "name": event.user.nickname, "avatar": event.user.avatar}
    if event.channel.id == DIRECT.id or event.channel.id.startswith("private:"):
        return base
    return base | {
        "channel_id": event.channel.id,
        "channel_name": event.channel.name,
        "channel_avatar": event.channel.avatar,
    }
