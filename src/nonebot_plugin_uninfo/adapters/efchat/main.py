from typing import Optional

from nonebot.adapters.efchat import Bot
from nonebot.adapters.efchat.event import (
    ChannelMessageEvent,
    InviteEvent,
    WhisperMessageEvent,
)

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Scene, SceneType, User


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(id=data["user_id"], name=data["user_id"], avatar=data.get("head"))

    def extract_scene(self, data):
        if "channel_id" in data:
            return Scene(
                id=data["channel_id"],
                type=SceneType.GROUP,
                name=data["channel_id"],
            )
        return Scene(id=data["user_id"], type=SceneType.PRIVATE, name=data["user_id"], avatar=data.get("head", None))

    def extract_member(self, data, user: Optional[User]):
        if user is None:
            user = self.extract_user(data)
        return Member(user, user.name)

    async def query_user(self, bot: Bot, user_id: str):
        return User(user_id, user_id)

    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ):
        return Scene(id=scene_id, type=scene_type, name=scene_id, avatar=None)

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        return Member(await self.query_user(bot, user_id), user_id)

    def query_users(self, bot: Bot):
        raise NotImplementedError

    def query_scenes(self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None):
        raise NotImplementedError

    def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        raise NotImplementedError

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.efchat,
            "scope": SupportScope.efchat,
        }


fetcher = InfoFetcher(SupportAdapter.efchat)


@fetcher.supply
async def _(bot: Bot, event: ChannelMessageEvent):
    return {"user_id": event.nick, "channel_id": event.channel, "head": event.head}


@fetcher.supply
async def _(bot: Bot, event: WhisperMessageEvent):
    return {
        "user_id": event.nick,
    }


@fetcher.supply
async def _(bot: Bot, event: InviteEvent):
    return {"user_id": event.nick, "channel_id": event.to}


@fetcher.supply_wildcard
async def _(bot: Bot, event):
    if hasattr(event, "nick"):
        return {"user_id": event.nick, "channel_id": bot.cfg.channel, "head": getattr(event, "head", None)}
    raise NotImplementedError
