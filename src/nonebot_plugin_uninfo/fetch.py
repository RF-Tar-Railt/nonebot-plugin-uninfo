from abc import ABCMeta, abstractmethod
from collections.abc import AsyncGenerator, Awaitable
from typing import Any, Callable, Optional, TypedDict, TypeVar, Union, get_args, get_origin, get_type_hints
from typing_extensions import NotRequired, Required

from nonebot.adapters import Bot, Event

from .constraint import SupportAdapter, SupportScope
from .model import Member, Scene, Session, User

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
        self.endpoint: dict[type[Event], Callable[[Bot, Event], Awaitable[dict]]] = {}
        self.wildcard: Optional[Callable[[Bot, Event], Awaitable[dict]]] = None

    def supply(self, func: TSupplier) -> TSupplier:
        event_type = get_type_hints(func)["event"]
        if get_origin(event_type) is Union:
            for t in get_args(event_type):
                self.endpoint[t] = func  # type: ignore
        else:
            self.endpoint[event_type] = func  # type: ignore
        return func

    def supply_wildcard(self, func: TSupplier) -> TSupplier:
        self.wildcard = func  # type: ignore
        return func

    @abstractmethod
    def extract_user(self, data: dict[str, Any]) -> User:
        pass

    @abstractmethod
    def extract_scene(self, data: dict[str, Any]) -> Scene:
        pass

    @abstractmethod
    def extract_member(self, data: dict[str, Any], user: Optional[User]) -> Optional[Member]:
        pass

    @abstractmethod
    def supply_self(self, bot) -> SuppliedData:
        pass

    def parse(self, data: dict) -> Session:
        user = self.extract_user(data)
        return Session(
            self_id=data["self_id"],
            adapter=data["adapter"],
            scope=data["scope"],
            user=user,
            scene=self.extract_scene(data),
            member=self.extract_member(data, user),
            operator=self.extract_member(data["operator"], None) if "operator" in data else None,  # type: ignore
        )

    async def fetch(self, bot: Bot, event: Event) -> Session:
        func = self.endpoint.get(type(event))
        base = self.supply_self(bot)
        try:
            if func:
                data = await func(bot, event)
                return self.parse({**base, **data})
            if self.wildcard:
                data = await self.wildcard(bot, event)
                return self.parse({**base, **data})
        except NotImplementedError:
            pass
        raise NotImplementedError(f"Event {type(event)} not supported yet")

    @abstractmethod
    def query_user(self, bot: Bot) -> AsyncGenerator[User, None]:
        pass

    @abstractmethod
    def query_scene(self, bot: Bot, guild_id: Optional[str]) -> AsyncGenerator[Scene, None]:
        pass

    @abstractmethod
    def query_member(self, bot: Bot, guild_id: str) -> AsyncGenerator[Member, None]:
        pass
