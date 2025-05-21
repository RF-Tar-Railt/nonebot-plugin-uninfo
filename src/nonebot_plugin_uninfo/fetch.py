from abc import ABCMeta, abstractmethod
import asyncio
from collections import defaultdict
from collections.abc import AsyncGenerator, Awaitable
from typing import Any, Callable, Optional, TypeVar, Union, get_args, get_origin, get_type_hints

from nonebot import get_plugin_config
from nonebot.adapters import Bot, Event

from .config import Config
from .constraint import SupportAdapter
from .model import BasicInfo, Member, Scene, SceneType, Session, User

TE = TypeVar("TE", bound=Event)
TB = TypeVar("TB", bound=Bot)
Supplier = Callable[[TB, TE], Awaitable[dict]]
TSupplier = TypeVar("TSupplier", bound=Supplier)

try:
    conf = get_plugin_config(Config)
except ValueError:
    conf = Config()


class InfoFetcher(metaclass=ABCMeta):
    def __init__(self, adapter: SupportAdapter):
        self.adapter = adapter
        self.endpoint: dict[type[Event], Callable[[Bot, Event], Awaitable[dict]]] = {}
        self.wildcard: Optional[Callable[[Bot, Event], Awaitable[dict]]] = None
        self.session_cache: dict[str, Session] = {}
        self._timertasks = []
        self._user_cache: defaultdict[str, dict[str, User]] = defaultdict(dict)
        self._scene_cache: defaultdict[str, dict[tuple[int, str, Optional[str]], Scene]] = defaultdict(dict)
        self._member_cache: defaultdict[str, dict[tuple[int, str, str], Member]] = defaultdict(dict)

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
    def supply_self(self, bot) -> BasicInfo:
        pass

    def get_session_id(self, event: Event) -> str:
        return event.get_session_id()

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
        try:
            sess_id = self.get_session_id(event)
        except ValueError:
            pass
        else:
            if sess_id in self.session_cache:
                return self.session_cache[sess_id]
        func = None
        for t in event.__class__.__mro__[:-1]:
            func = self.endpoint.get(t)
            if func:
                break
        base = self.supply_self(bot)
        try:
            if func:
                data = await func(bot, event)
                sess = self.parse({**base, **data})
            elif self.wildcard:
                data = await self.wildcard(bot, event)
                sess = self.parse({**base, **data})
            else:
                raise NotImplementedError(f"Event {type(event)} not supported yet")
        except NotImplementedError:
            raise NotImplementedError(f"Event {type(event)} not supported yet") from None
        if conf.uninfo_cache:
            try:
                sess_id = self.get_session_id(event)
                self.session_cache[sess_id] = sess
                asyncio.get_running_loop().call_later(conf.uninfo_cache_expire, self.session_cache.pop, sess_id, None)
                key1 = sess.user.id
                self._user_cache[bot.self_id][key1] = sess.user
                asyncio.get_running_loop().call_later(
                    conf.uninfo_cache_expire, self._user_cache[bot.self_id].pop, key1, None
                )
                key2 = (sess.scene.type.value, sess.scene.id, sess.scene.parent.id if sess.scene.parent else None)
                self._scene_cache[bot.self_id][key2] = sess.scene
                asyncio.get_running_loop().call_later(
                    conf.uninfo_cache_expire, self._scene_cache[bot.self_id].pop, key2, None
                )
                if sess.member:
                    key3 = (
                        sess.scene.type.value,
                        sess.scene.parent.id if sess.scene.parent else sess.scene.id,
                        sess.member.id,
                    )
                    self._member_cache[bot.self_id][key3] = sess.member
                    asyncio.get_running_loop().call_later(
                        conf.uninfo_cache_expire, self._member_cache[bot.self_id].pop, key3, None
                    )
            except ValueError:
                pass
        return sess

    @abstractmethod
    async def query_user(self, bot: Bot, user_id: str) -> Optional[User]:
        pass

    async def fetch_user(self, bot: Bot, user_id: str) -> Optional[User]:
        if user_id in self._user_cache[bot.self_id]:
            return self._user_cache[bot.self_id][user_id]
        user = await self.query_user(bot, user_id)
        if user and conf.uninfo_cache:
            self._user_cache[bot.self_id][user_id] = user
            asyncio.get_running_loop().call_later(
                conf.uninfo_cache_expire, self._user_cache[bot.self_id].pop, user_id, None
            )
        return user

    @abstractmethod
    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ) -> Optional[Scene]:
        pass

    async def fetch_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ) -> Optional[Scene]:
        key = (scene_type.value, scene_id, parent_scene_id)
        if key in self._scene_cache[bot.self_id]:
            return self._scene_cache[bot.self_id][key]
        scene = await self.query_scene(bot, scene_type, scene_id, parent_scene_id=parent_scene_id)
        if scene and conf.uninfo_cache:
            self._scene_cache[bot.self_id][key] = scene
            asyncio.get_running_loop().call_later(
                conf.uninfo_cache_expire, self._scene_cache[bot.self_id].pop, key, None
            )
        return scene

    @abstractmethod
    async def query_member(
        self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str
    ) -> Optional[Member]:
        pass

    async def fetch_member(
        self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str
    ) -> Optional[Member]:
        key = (scene_type.value, parent_scene_id, user_id)
        if key in self._member_cache[bot.self_id]:
            return self._member_cache[bot.self_id][key]
        member = await self.query_member(bot, scene_type, parent_scene_id, user_id)
        if member and conf.uninfo_cache:
            self._member_cache[bot.self_id][key] = member
            asyncio.get_running_loop().call_later(
                conf.uninfo_cache_expire, self._member_cache[bot.self_id].pop, key, None
            )
        return member

    @abstractmethod
    def query_users(self, bot: Bot) -> AsyncGenerator[User, None]:
        pass

    @abstractmethod
    def query_scenes(
        self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None
    ) -> AsyncGenerator[Scene, None]:
        pass

    @abstractmethod
    def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str) -> AsyncGenerator[Member, None]:
        pass
