from typing import Callable, TypeVar
from collections.abc import Awaitable

from nonebot.adapters import Event, Bot
from .constraint import SupportAdapter
from .model import Session


TE = TypeVar("TE", bound=Event)


class InfoFetcher:
    def __init__(self, adapter: SupportAdapter):
        self.adapter = adapter
        self.endpoint: dict[type[Event], Callable[[Bot, Event], Awaitable[Session]]] = {}

    def register(self, event: type[TE]):
        def decorator(func: Callable[[Bot, TE], Awaitable[Session]]):
            self.endpoint[event] = func  # type: ignore
            return func
        return decorator
