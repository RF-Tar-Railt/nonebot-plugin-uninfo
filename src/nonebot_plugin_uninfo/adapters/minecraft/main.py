from typing import Optional

from nonebot.adapters.minecraft import Bot
from nonebot.adapters.minecraft.event.base import Event, MessageEvent, NoticeEvent

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.fetch import SuppliedData
from nonebot_plugin_uninfo.model import Scene, SceneType, User


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
        )

    def extract_scene(self, data):
        return Scene(
            id=data["user_id"],
            type=SceneType.PRIVATE,
            name=data["name"],
        )

    def extract_member(self, data, user: Optional[User]):
        return None

    async def query_user(self, bot: Bot):
        raise NotImplementedError

    async def query_scene(self, bot: Bot, guild_id: Optional[str]):
        raise NotImplementedError

    async def query_member(self, bot: Bot, guild_id: str):
        raise NotImplementedError

    def supply_self(self, bot: Bot) -> SuppliedData:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.minecraft,
            "scope": SupportScope.minecraft,
        }


fetcher = InfoFetcher(SupportAdapter.minecraft)


@fetcher.supply_wildcard
async def _(bot: Bot, event: Event):
    if isinstance(event, (MessageEvent, NoticeEvent)):
        return {
            "user_id": str(event.player.uuid or event.player.nickname),
            "name": event.player.nickname,
        }
    raise NotImplementedError
