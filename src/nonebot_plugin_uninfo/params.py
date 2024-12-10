from typing import Annotated, Optional

from nonebot.adapters import Bot
from nonebot.params import Depends

from .adapters import INFO_FETCHER_MAPPING, alter_get_fetcher
from .fetch import InfoFetcher
from .model import Member, Scene, SceneType, Session, User


async def get_session(bot: Bot, event):
    adapter = bot.adapter.get_name()
    fetcher = INFO_FETCHER_MAPPING.get(adapter)
    if not fetcher:
        fetcher = alter_get_fetcher(adapter)
    if fetcher:
        try:
            return await fetcher.fetch(bot, event)
        except NotImplementedError:
            pass
    return None


def UniSession() -> Session:
    return Depends(get_session)


Uninfo = Annotated[Session, UniSession()]


class Interface:
    def __init__(self, bot: Bot, fetcher: InfoFetcher):
        self.bot = bot
        self.fetcher = fetcher

    def basic_info(self):
        return self.fetcher.supply_self(self.bot)

    async def get_user(self, user_id: str) -> Optional[User]:
        try:
            return await self.fetcher.fetch_user(self.bot, user_id)
        except NotImplementedError:
            pass

        async for user in self.iter_users():
            if user.id == user_id:
                return user

    async def get_scene(
        self, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ) -> Optional[Scene]:
        try:
            return await self.fetcher.fetch_scene(self.bot, scene_type, scene_id, parent_scene_id=parent_scene_id)
        except NotImplementedError:
            pass

        async for scene in self.iter_scenes(scene_type, parent_scene_id=parent_scene_id):
            if scene.type == scene_type and scene.id == scene_id:
                return scene

    async def get_member(self, scene_type: SceneType, scene_id: str, user_id: str) -> Optional[Member]:
        try:
            return await self.fetcher.fetch_member(self.bot, scene_type, scene_id, user_id)
        except NotImplementedError:
            pass

        async for member in self.iter_members(scene_type, scene_id):
            if member.user.id == user_id:
                return member

    async def get_users(self) -> list[User]:
        ans = []
        async for user in self.iter_users():
            ans.append(user)
        return ans

    async def get_scenes(
        self, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None
    ) -> list[Scene]:
        ans = []
        async for scene in self.iter_scenes(scene_type, parent_scene_id=parent_scene_id):
            ans.append(scene)
        return ans

    async def get_members(self, scene_type: SceneType, scene_id: str) -> list[Member]:
        ans = []
        async for member in self.iter_members(scene_type, scene_id):
            ans.append(member)
        return ans

    async def iter_users(self):
        try:
            async for user in self.fetcher.query_users(self.bot):
                yield user
        except NotImplementedError:
            return

    async def iter_scenes(self, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None):
        try:
            async for scene in self.fetcher.query_scenes(self.bot, scene_type, parent_scene_id=parent_scene_id):
                yield scene
        except NotImplementedError:
            return

    async def iter_members(self, scene_type: SceneType, scene_id: str):
        try:
            async for member in self.fetcher.query_members(self.bot, scene_type, scene_id):
                yield member
        except NotImplementedError:
            return


def get_interface(bot: Bot):
    adapter = bot.adapter.get_name()
    fetcher = INFO_FETCHER_MAPPING.get(adapter)
    if fetcher:
        return Interface(bot, fetcher)
    return None


def QueryInterface() -> Interface:
    return Depends(get_interface)


QryItrface = Annotated[Interface, QueryInterface()]
