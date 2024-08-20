from nonebot.adapters import Bot
from nonebot.params import Depends
from typing import Annotated

from .model import Session as Session
from .adapters import INFO_FETCHER_MAPPING


async def get_session(bot: Bot, event):
    adapter = bot.adapter.get_name()
    fetcher = INFO_FETCHER_MAPPING.get(adapter)
    if fetcher:
        return await fetcher.fetch(bot, event)
    return None

def UniSession() -> Session:
    return Depends(get_session)


Uninfo = Annotated[Session, UniSession()]
