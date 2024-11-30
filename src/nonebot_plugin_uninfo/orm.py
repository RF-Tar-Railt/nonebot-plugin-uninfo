import asyncio
import json
import sys
from typing import Optional

from nonebot import get_bots, require
from nonebot.adapters import Bot
from nonebot.params import Depends

from .model import BasicInfo, Member, Scene, SceneType, Session, User
from .params import UniSession, get_interface

try:
    require("nonebot_plugin_orm")
    from nonebot_plugin_orm import Model, get_session
    from sqlalchemy import JSON, Integer, String, UniqueConstraint, exc, select
    from sqlalchemy.orm import Mapped, mapped_column
except ImportError:
    raise ImportError("You need to install nonebot_plugin_orm to use this module.")


class BotModel(Model):
    __tablename__ = "nonebot_plugin_uninfo_botmodel"
    __table_args__ = (
        UniqueConstraint(
            "self_id",
            "adapter",
            name="unique_bot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    self_id: Mapped[str] = mapped_column(String(64))
    adapter: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(32))

    def get_bot(self) -> Optional[Bot]:
        for bot in list(get_bots().values()):
            if bot.self_id == self.self_id and bot.adapter.get_name() == self.adapter:
                return bot


class SceneModel(Model):
    __tablename__ = "nonebot_plugin_uninfo_scenemodel"
    __table_args__ = (
        UniqueConstraint(
            "bot_persist_id",
            "scene_id",
            "scene_type",
            name="unique_scene",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_persist_id: Mapped[int] = mapped_column(Integer)
    parent_scene_persist_id: Mapped[Optional[int]] = mapped_column(Integer)
    scene_id: Mapped[str] = mapped_column(String(64))
    scene_type: Mapped[int] = mapped_column(Integer)
    scene_data: Mapped[dict] = mapped_column(JSON)

    async def to_scene(self) -> Scene:
        parent_scene_model = (
            await get_scene_model(self.parent_scene_persist_id) if self.parent_scene_persist_id else None
        )
        return Scene.load(
            {
                **self.scene_data,
                "id": self.scene_id,
                "type": self.scene_type,
                "parent": (
                    {
                        **parent_scene_model.scene_data,
                        "id": parent_scene_model.scene_id,
                        "type": parent_scene_model.scene_type,
                    }
                    if parent_scene_model
                    else None
                ),
            }
        )

    async def query_scene(self) -> Optional[Scene]:
        bot_model = await get_bot_model(self.bot_persist_id)
        if not (bot := bot_model.get_bot()):
            return None
        if not (interface := get_interface(bot)):
            return None

        scene = await self.to_scene()
        return await interface.get_scene(
            SceneType(scene.type), scene.id, parent_scene_id=scene.parent.id if scene.parent else None
        )


class UserModel(Model):
    __tablename__ = "nonebot_plugin_uninfo_usermodel"
    __table_args__ = (
        UniqueConstraint(
            "bot_persist_id",
            "user_id",
            name="unique_user",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_persist_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[str] = mapped_column(String(64))
    user_data: Mapped[dict] = mapped_column(JSON)

    async def to_user(self) -> User:
        return User(**{**self.user_data, "id": self.user_id})

    async def query_user(self) -> Optional[User]:
        bot_model = await get_bot_model(self.bot_persist_id)
        if not (bot := bot_model.get_bot()):
            return None
        if not (interface := get_interface(bot)):
            return None

        return await interface.get_user(self.user_id)


class SessionModel(Model):
    __tablename__ = "nonebot_plugin_uninfo_sessionmodel"
    __table_args__ = (
        UniqueConstraint(
            "bot_persist_id",
            "scene_persist_id",
            "user_persist_id",
            name="unique_session",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_persist_id: Mapped[int] = mapped_column(Integer)
    scene_persist_id: Mapped[int] = mapped_column(Integer)
    user_persist_id: Mapped[int] = mapped_column(Integer)
    member_data: Mapped[Optional[dict]] = mapped_column(JSON)

    async def to_session(self) -> Session:
        bot_model = await get_bot_model(self.bot_persist_id)
        scene_model = await get_scene_model(self.scene_persist_id)
        scene = await scene_model.to_scene()
        user_model = await get_user_model(self.user_persist_id)
        user = await user_model.to_user()
        member = Member.load(self.member_data) if self.member_data else None

        return Session(
            self_id=bot_model.self_id,
            adapter=bot_model.adapter,
            scope=bot_model.scope,
            scene=scene,
            user=user,
            member=member,
        )

    async def query_session(self) -> Optional[Session]:
        bot_model = await get_bot_model(self.bot_persist_id)
        if not (bot := bot_model.get_bot()):
            return None
        if not (interface := get_interface(bot)):
            return None

        scene_model = await get_scene_model(self.scene_persist_id)
        scene = await scene_model.to_scene()
        if not (
            scene := await interface.get_scene(
                SceneType(scene.type), scene.id, parent_scene_id=scene.parent.id if scene.parent else None
            )
        ):
            return None

        user_model = await get_user_model(self.user_persist_id)
        if not (user := await interface.get_user(user_model.user_id)):
            return None

        member = await interface.get_member(SceneType(scene_model.scene_type), scene_model.scene_id, user_model.user_id)

        return Session(
            self_id=bot_model.self_id,
            adapter=bot_model.adapter,
            scope=bot_model.scope,
            scene=scene,
            user=user,
            member=member,
        )


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


async def get_bot_persist_id(basic_info: BasicInfo) -> int:
    statement = (
        select(BotModel)
        .where(BotModel.self_id == basic_info["self_id"])
        .where(BotModel.adapter == basic_info["adapter"].value)
    )
    async with get_session() as db_session:
        if bot_model := (await db_session.scalars(statement)).one_or_none():
            bot_model.scope = basic_info["scope"].value
            await db_session.commit()
            await db_session.refresh(bot_model)
            return bot_model.id

    bot_model = BotModel(
        self_id=basic_info["self_id"],
        adapter=basic_info["adapter"].value,
        scope=basic_info["scope"].value,
    )
    async with _get_insert_mutex():
        try:
            async with get_session() as db_session:
                db_session.add(bot_model)
                await db_session.commit()
                await db_session.refresh(bot_model)
                return bot_model.id
        except exc.IntegrityError:
            async with get_session() as db_session:
                return (await db_session.scalars(statement)).one().id


async def get_scene_persist_id(basic_info: BasicInfo, scene: Scene) -> int:
    bot_persist_id = await get_bot_persist_id(basic_info)
    parent_scene_persist_id = await get_scene_persist_id(basic_info, scene.parent) if scene.parent else None
    scene_data = json.loads(scene.dump_json())

    statement = (
        select(SceneModel)
        .where(SceneModel.bot_persist_id == bot_persist_id)
        .where(SceneModel.scene_id == scene.id)
        .where(SceneModel.scene_type == scene.type.value)
    )
    async with get_session() as db_session:
        if scene_model := (await db_session.scalars(statement)).one_or_none():
            scene_model.parent_scene_persist_id = parent_scene_persist_id
            scene_model.scene_data = scene_data
            await db_session.commit()
            await db_session.refresh(scene_model)
            return scene_model.id

    scene_model = SceneModel(
        bot_persist_id=bot_persist_id,
        parent_scene_persist_id=parent_scene_persist_id,
        scene_id=scene.id,
        scene_type=scene.type.value,
        scene_data=scene_data,
    )
    async with _get_insert_mutex():
        try:
            async with get_session() as db_session:
                db_session.add(scene_model)
                await db_session.commit()
                await db_session.refresh(scene_model)
                return scene_model.id
        except exc.IntegrityError:
            async with get_session() as db_session:
                return (await db_session.scalars(statement)).one().id


async def get_user_persist_id(basic_info: BasicInfo, user: User) -> int:
    bot_persist_id = await get_bot_persist_id(basic_info)
    user_data = json.loads(user.dump_json())

    statement = select(UserModel).where(UserModel.bot_persist_id == bot_persist_id).where(UserModel.user_id == user.id)
    async with get_session() as db_session:
        if user_model := (await db_session.scalars(statement)).one_or_none():
            user_model.user_data = user_data
            await db_session.commit()
            await db_session.refresh(user_model)
            return user_model.id

    user_model = UserModel(
        bot_persist_id=bot_persist_id,
        user_id=user.id,
        user_data=user_data,
    )
    async with _get_insert_mutex():
        try:
            async with get_session() as db_session:
                db_session.add(user_model)
                await db_session.commit()
                await db_session.refresh(user_model)
                return user_model.id
        except exc.IntegrityError:
            async with get_session() as db_session:
                return (await db_session.scalars(statement)).one().id


async def get_session_persist_id(session: Session) -> int:
    bot_persist_id = await get_bot_persist_id(session.basic)
    scene_persist_id = await get_scene_persist_id(session.basic, session.scene)
    user_persist_id = await get_user_persist_id(session.basic, session.user)
    member_data = json.loads(session.member.dump_json()) if session.member else None

    statement = (
        select(SessionModel)
        .where(SessionModel.bot_persist_id == bot_persist_id)
        .where(SessionModel.scene_persist_id == scene_persist_id)
        .where(SessionModel.user_persist_id == user_persist_id)
    )
    async with get_session() as db_session:
        if session_model := (await db_session.scalars(statement)).one_or_none():
            session_model.member_data = member_data
            await db_session.commit()
            await db_session.refresh(session_model)
            return session_model.id

    session_model = SessionModel(
        bot_persist_id=bot_persist_id,
        scene_persist_id=scene_persist_id,
        user_persist_id=user_persist_id,
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
            async with get_session() as db_session:
                return (await db_session.scalars(statement)).one().id


async def get_bot_model(persist_id: int) -> BotModel:
    async with get_session() as db_session:
        return (await db_session.scalars(select(BotModel).where(BotModel.id == persist_id))).one()


async def get_scene_model(persist_id: int) -> SceneModel:
    async with get_session() as db_session:
        return (await db_session.scalars(select(SceneModel).where(SceneModel.id == persist_id))).one()


async def get_user_model(persist_id: int) -> UserModel:
    async with get_session() as db_session:
        return (await db_session.scalars(select(UserModel).where(UserModel.id == persist_id))).one()


async def get_session_model(persist_id: int) -> SessionModel:
    async with get_session() as db_session:
        return (await db_session.scalars(select(SessionModel).where(SessionModel.id == persist_id))).one()


async def get_bot_orm(session: Session = UniSession()):
    return await get_bot_model(await get_bot_persist_id(session.basic))


def BotOrm() -> BotModel:
    return Depends(get_bot_orm)


async def get_scene_orm(session: Session = UniSession()):
    return await get_scene_model(await get_scene_persist_id(session.basic, session.scene))


def SceneOrm() -> SceneModel:
    return Depends(get_scene_orm)


async def get_user_orm(session: Session = UniSession()):
    return await get_user_model(await get_user_persist_id(session.basic, session.user))


def UserOrm() -> UserModel:
    return Depends(get_user_orm)


async def get_session_orm(session: Session = UniSession()):
    return await get_session_model(await get_session_persist_id(session))


def SessionOrm() -> SessionModel:
    return Depends(get_session_orm)
