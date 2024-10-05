import asyncio
import sys
from typing import Optional

from nonebot import get_bots, require
from nonebot.log import logger
from nonebot.params import Depends

from .model import Member, Scene, SceneType, Session, User
from .params import UniSession, get_interface

try:
    require("nonebot_plugin_orm")
    from nonebot_plugin_orm import Model, get_session
    from sqlalchemy import JSON, Integer, String, UniqueConstraint, exc, select
    from sqlalchemy.orm import Mapped, mapped_column
    from sqlalchemy.sql import ColumnElement
except ImportError:
    raise ImportError("You need to install nonebot_plugin_orm to use this module.")


class SessionModel(Model):
    __table_args__ = (
        UniqueConstraint(
            "self_id",
            "adapter",
            "scope",
            "scene_type",
            "scene_id",
            "parent_scene_type",
            "parent_scene_id",
            "user_id",
            name="unique_session",
        ),
    )
    __tablename__ = "nonebot_plugin_uninfo_sessionmodel"

    id: Mapped[int] = mapped_column(primary_key=True)
    self_id: Mapped[str] = mapped_column(String(64))
    adapter: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(32))
    scene_id: Mapped[str] = mapped_column(String(64))
    scene_type: Mapped[int] = mapped_column(Integer)
    scene_data: Mapped[dict] = mapped_column(JSON)
    parent_scene_id: Mapped[str] = mapped_column(String(64))
    parent_scene_type: Mapped[int] = mapped_column(Integer)
    parent_scene_data: Mapped[Optional[dict]] = mapped_column(JSON)
    user_id: Mapped[str] = mapped_column(String(64))
    user_data: Mapped[dict] = mapped_column(JSON)
    member_data: Mapped[Optional[dict]] = mapped_column(JSON)

    def to_session(self) -> Session:
        return Session(
            self_id=self.self_id,
            adapter=self.adapter,
            scope=self.scope,
            scene=Scene(
                **{
                    **self.scene_data,
                    "id": self.scene_id,
                    "type": SceneType(self.scene_type),
                    "parent": (
                        Scene(
                            **{
                                **(self.parent_scene_data or {}),
                                "id": self.parent_scene_id,
                                "type": SceneType(self.parent_scene_type),
                            }
                        )
                        if self.parent_scene_id
                        else None
                    ),
                }
            ),
            user=User(**{**self.user_data, "id": self.user_id}),
            member=Member.load(self.member_data) if self.member_data else None,
        )

    async def query_session(self) -> Optional[Session]:
        bot = None
        for _bot in list(get_bots().values()):
            if _bot.self_id == self.self_id and _bot.adapter.get_name() == self.adapter:
                bot = _bot
                break
        if not bot:
            return None

        interface = get_interface(bot)
        if not interface:
            return None

        scene = await interface.get_scene(
            SceneType(self.scene_type), self.scene_id, parent_scene_id=(self.parent_scene_id or None)
        )
        if not scene:
            return None

        user = None
        member = await interface.get_member(SceneType(self.scene_type), self.scene_id, self.user_id)
        if member:
            user = member.user

        if not user:
            user = await interface.get_user(self.user_id)
        if not user:
            return None

        return Session(
            self_id=self.self_id,
            adapter=self.adapter,
            scope=self.scope,
            scene=scene,
            user=user,
            member=member,
        )

    @staticmethod
    def filter_statement(
        session: Session,
        *,
        filter_self_id: bool = True,
        filter_adapter: bool = True,
        filter_scope: bool = True,
        filter_scene: bool = True,
        filter_user: bool = True,
    ) -> list[ColumnElement[bool]]:
        whereclause: list[ColumnElement[bool]] = []
        if filter_self_id:
            whereclause.append(SessionModel.self_id == session.self_id)
        if filter_adapter:
            whereclause.append(SessionModel.adapter == session.adapter)
        if filter_scope:
            whereclause.append(SessionModel.scope == session.scope)
        if filter_scene:
            whereclause.append(SessionModel.scene_id == session.scene.id)
            whereclause.append(SessionModel.scene_type == session.scene.type.value)
            if session.scene.parent:
                whereclause.append(SessionModel.parent_scene_id == session.scene.parent.id)
                whereclause.append(SessionModel.parent_scene_type == session.scene.parent.type.value)
        if filter_user:
            whereclause.append(SessionModel.user_id == session.user.id)
        return whereclause


_insert_mutex: Optional[asyncio.Lock] = None


def _get_insert_mutex():
    # py3.10以下，Lock必须在event_loop内创建
    global _insert_mutex

    if _insert_mutex is None:
        _insert_mutex = asyncio.Lock()
    elif sys.version_info < (3, 10):
        # 还需要判断loop是否与之前创建的一致
        # 单测中不同的test，loop也不一样
        # 但是nonebot里loop始终是一样的
        if getattr(_insert_mutex, "_loop") != asyncio.get_running_loop():
            _insert_mutex = asyncio.Lock()

    return _insert_mutex


async def get_session_persist_id(session: Session) -> int:
    parent_scene_id = session.scene.parent.id if session.scene.parent else ""
    parent_scene_type = session.scene.parent.type.value if session.scene.parent else -1
    parent_scene_data = session.scene.parent.dump() if session.scene.parent else None
    member_data = session.member.dump() if session.member else None

    statement = (
        select(SessionModel)
        .where(SessionModel.self_id == session.self_id)
        .where(SessionModel.adapter == session.adapter)
        .where(SessionModel.scope == session.scope)
        .where(SessionModel.scene_id == session.scene.id)
        .where(SessionModel.scene_type == session.scene.type.value)
        .where(SessionModel.user_id == session.user.id)
    )

    if session.scene.parent:
        statement = statement.where(SessionModel.parent_scene_id == parent_scene_id)
        statement = statement.where(SessionModel.parent_scene_type == parent_scene_type)

    async with get_session() as db_session:
        if persist_model := (await db_session.scalars(statement)).one_or_none():
            persist_model.scene_data = session.scene.dump()
            persist_model.parent_scene_data = parent_scene_data
            persist_model.user_data = session.user.dump()
            persist_model.member_data = member_data
            await db_session.commit()
            await db_session.refresh(persist_model)
            return persist_model.id

    session_model = SessionModel(
        self_id=session.self_id,
        adapter=session.adapter,
        scope=session.scope,
        scene_id=session.scene.id,
        scene_type=session.scene.type.value,
        scene_data=session.scene.dump(),
        parent_scene_id=parent_scene_id,
        parent_scene_type=parent_scene_type,
        parent_scene_data=parent_scene_data,
        user_id=session.user.id,
        user_data=session.user.dump(),
        member_data=member_data,
    )

    async with _get_insert_mutex():
        try:
            async with get_session() as db_session:
                db_session.add(session_model)
                await db_session.commit()
                await db_session.refresh(session_model)
                return session_model.id
        except exc.IntegrityError:
            logger.debug(f"session ({session}) is already inserted")

            async with get_session() as db_session:
                return (await db_session.scalars(statement)).one().id


async def get_session_model(persist_id: int) -> SessionModel:
    async with get_session() as db_session:
        return (await db_session.scalars(select(SessionModel).where(SessionModel.id == persist_id))).one()


async def get_session_orm(session: Session = UniSession()):
    return await get_session_model(await get_session_persist_id(session))


def SessionOrm() -> SessionModel:
    return Depends(get_session_orm)
