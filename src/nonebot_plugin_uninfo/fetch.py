from abc import ABCMeta, abstractmethod
from typing import Callable, TypeVar, Optional, TypedDict, Any
from typing_extensions import Required
from collections.abc import Awaitable, AsyncGenerator

from nonebot.adapters import Event, Bot
from .constraint import SupportAdapter, SupportScope
from .model import Session, User, Channel, Guild, Member


TE = TypeVar("TE", bound=Event)
TB = TypeVar("TB", bound=Bot)


class SuppliedData(TypedDict, total=False):
    self_id: Required[str]
    adapter: Required[SupportAdapter]
    scope: Required[SupportScope]


class InfoFetcher(metaclass=ABCMeta):
    def __init__(self, adapter: SupportAdapter):
        self.adapter = adapter
        self.endpoint: dict[type[Event], Callable[[Bot, Event], Awaitable[SuppliedData]]] = {}

    def register(self, event: type[TE]):# -> Callable[..., Callable[[TB, TE], Awaitable[Session]]]:
        def decorator(func: Callable[[TB, TE], Awaitable[dict]]):
            self.endpoint[event] = func  # type: ignore
            return func
        return decorator
    
    @abstractmethod
    def extract_user(self, data: dict[str, Any]) -> User:
        pass

    @abstractmethod
    def extract_channel(self, data: dict[str, Any]) -> Channel:
        pass

    @abstractmethod
    def extract_guild(self, data: dict[str, Any]) -> Optional[Guild]:
        pass

    @abstractmethod
    def extract_member(self, data: dict[str, Any]) -> Optional[Member]:
        pass

    def parse(self, data: SuppliedData) -> Session:
        return Session(
            self_id=data["self_id"],
            adapter=data["adapter"],
            scope=data["scope"],
            user=self.extract_user(data),  # type: ignore
            channel=self.extract_channel(data),  # type: ignore
            guild=self.extract_guild(data),  # type: ignore
            member=self.extract_member(data)  # type: ignore
        )


    async def fetch(self, bot: Bot, event: Event) -> Session:
        func = self.endpoint.get(type(event))
        if func:
            data = await func(bot, event)
            return self.parse(data)
        raise NotImplementedError(f"Event {type(event)} not supported yet")

    @abstractmethod
    def query_user(self, bot: Bot) -> AsyncGenerator[User, None]:
        pass

    @abstractmethod
    def query_channel(self, bot: Bot, guild_id: str) -> AsyncGenerator[Channel, None]:
        pass

    @abstractmethod
    def query_guild(self, bot: Bot) -> AsyncGenerator[Guild, None]:
        pass

    @abstractmethod
    def query_member(self, bot: Bot, guild_id: str) -> AsyncGenerator[Member, None]:
        pass
