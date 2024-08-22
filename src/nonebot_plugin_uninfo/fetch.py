from abc import ABCMeta, abstractmethod
from typing import Callable, TypeVar, Optional, TypedDict, Any, Union, get_type_hints, get_origin, get_args
from typing_extensions import Required, NotRequired
from collections.abc import Awaitable, AsyncGenerator

from nonebot.adapters import Event, Bot
from .constraint import SupportAdapter, SupportScope
from .model import Session, User, Channel, Guild, Member


TE = TypeVar("TE", bound=Event)
TB = TypeVar("TB", bound=Bot)
Supplier = Callable[[TB, TE], Awaitable[dict]]
TSupplier = TypeVar("TSupplier", bound=Supplier)


class SuppliedData(TypedDict, total=False):
    self_id: Required[str]
    adapter: Required[SupportAdapter]
    scope: Required[SupportScope]

    operator: NotRequired[dict]


class InfoFetcher(metaclass=ABCMeta):
    def __init__(self, adapter: SupportAdapter):
        self.adapter = adapter
        self.endpoint: dict[type[Event], Callable[[Bot, Event], Awaitable[SuppliedData]]] = {}

    def supply(self, func: TSupplier) -> TSupplier:
        event_type = get_type_hints(func)["event"]
        if get_origin(event_type) is Union:
            for t in get_args(event_type):
                self.endpoint[t] = func  # type: ignore
        else:
            self.endpoint[event_type] = func  # type: ignore
        return func

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
    def extract_member(self, data: dict[str, Any], user: Optional[User]) -> Optional[Member]:
        pass

    def parse(self, data: SuppliedData) -> Session:
        user = self.extract_user(data)  # type: ignore
        return Session(
            self_id=data["self_id"],
            adapter=data["adapter"],
            scope=data["scope"],
            user=user,
            channel=self.extract_channel(data),  # type: ignore
            guild=self.extract_guild(data),  # type: ignore
            member=self.extract_member(data, user),  # type: ignore
            operator=self.extract_member(data["operator"], None) if "operator" in data else None  # type: ignore
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
