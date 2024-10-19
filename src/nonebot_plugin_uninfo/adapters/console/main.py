from typing import Optional

from nonebot.adapters.console import Bot
from nonebot.adapters.console.event import Event

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Scene, SceneType, User


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            avatar=data["avatar"],
        )

    def extract_scene(self, data):
        return Scene(
            id=data["user_id"],
            type=SceneType.PRIVATE,
            name=data["name"],
            avatar=data["avatar"],
        )

    def extract_member(self, data, user: Optional[User]):
        return None

    async def query_user(self, bot: Bot, user_id: str):
        raise NotImplementedError

    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ):
        raise NotImplementedError

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        raise NotImplementedError

    def query_users(self, bot: Bot):
        raise NotImplementedError

    def query_scenes(self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None):
        raise NotImplementedError

    def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        raise NotImplementedError

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.console,
            "scope": SupportScope.console,
        }


fetcher = InfoFetcher(SupportAdapter.console)


@fetcher.supply_wildcard
async def _(bot: Bot, event: Event):
    return {
        "user_id": event.user.id,
        "name": event.user.nickname,
        "avatar": f"https://emojicdn.elk.sh/{event.user.avatar}?style=twitter",
    }
