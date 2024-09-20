from typing import Annotated, Optional

from nonebot.adapters import Bot
from nonebot.params import Depends

from .adapters import INFO_FETCHER_MAPPING
from .fetch import InfoFetcher
from .model import Member, Scene, Session, User


async def get_session(bot: Bot, event):
    adapter = bot.adapter.get_name()
    fetcher = INFO_FETCHER_MAPPING.get(adapter)
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

    async def get_users(self) -> list[User]:
        ans = []
        async for user in self.iter_users():
            ans.append(user)
        return ans

    async def get_scenes(self, guild_id: Optional[str] = None) -> list[Scene]:
        ans = []
        async for scene in self.iter_scenes(guild_id):
            ans.append(scene)
        return ans

    async def get_members(self, guild_id: str) -> list[Member]:
        ans = []
        async for member in self.iter_members(guild_id):
            ans.append(member)
        return ans

    async def iter_users(self):
        try:
            async for user in self.fetcher.query_user(self.bot):
                yield user
        except NotImplementedError:
            return

    async def iter_scenes(self, guild_id: Optional[str] = None):
        try:
            async for scene in self.fetcher.query_scene(self.bot, guild_id):
                yield scene
        except NotImplementedError:
            return

    async def iter_members(self, guild_id: str):
        try:
            async for member in self.fetcher.query_member(self.bot, guild_id):
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
