from typing import Annotated

from nonebot.adapters import Bot
from nonebot.params import Depends

from .adapters import INFO_FETCHER_MAPPING
from .model import Session as Session


async def get_session(bot: Bot, event):
    adapter = bot.adapter.get_name()
    fetcher = INFO_FETCHER_MAPPING.get(adapter)
    if fetcher:
        return await fetcher.fetch(bot, event)
    return None


def UniSession() -> Session:
    return Depends(get_session)


Uninfo = Annotated[Session, UniSession()]
