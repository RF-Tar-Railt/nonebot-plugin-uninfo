import asyncio
import sys
from typing import Optional

from nonebot import get_bots, require
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
    bot_persist_id: Mapped[int]
    parent_scene_persist_id: Mapped[Optional[int]]
    scene_id: Mapped[str] = mapped_column(String(64))
    scene_type: Mapped[int] = mapped_column(Integer)
    scene_data: Mapped[dict] = mapped_column(JSON)


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
    bot_persist_id: Mapped[int]
    user_id: Mapped[str] = mapped_column(String(64))
    user_data: Mapped[dict] = mapped_column(JSON)


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
    bot_persist_id: Mapped[int]
    scene_persist_id: Mapped[int]
    user_persist_id: Mapped[int]
    member_data: Mapped[Optional[dict]] = mapped_column(JSON)

    async def to_session(self) -> Session:
        parent_scene_model = None
        async with get_session() as db_session:
            bot_model = (await db_session.scalars(select(BotModel).where(BotModel.id == self.bot_persist_id))).one()
            scene_model = (
                await db_session.scalars(select(SceneModel).where(SceneModel.id == self.scene_persist_id))
            ).one()
            user_model = (await db_session.scalars(select(UserModel).where(UserModel.id == self.user_persist_id))).one()

            if scene_model.parent_scene_persist_id:
                parent_scene_model = (
                    await db_session.scalars(
                        select(SceneModel).where(SceneModel.id == scene_model.parent_scene_persist_id)
                    )
                ).one()

        scene = Scene.load(
            {
                **scene_model.scene_data,
                "id": scene_model.scene_id,
                "type": scene_model.scene_type,
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
        user = User(**{**user_model.user_data, "id": user_model.user_id})
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
        parent_scene_id = None
        async with get_session() as db_session:
            bot_model = (await db_session.scalars(select(BotModel).where(BotModel.id == self.bot_persist_id))).one()
            scene_model = (
                await db_session.scalars(select(SceneModel).where(SceneModel.id == self.scene_persist_id))
            ).one()
            user_model = (await db_session.scalars(select(UserModel).where(UserModel.id == self.user_persist_id))).one()

            if scene_model.parent_scene_persist_id:
                parent_scene_model = (
                    await db_session.scalars(
                        select(SceneModel).where(SceneModel.id == scene_model.parent_scene_persist_id)
                    )
                ).one()
                parent_scene_id = parent_scene_model.scene_id

        bot = None
        for _bot in list(get_bots().values()):
            if _bot.self_id == bot_model.self_id and _bot.adapter.get_name() == bot_model.adapter:
                bot = _bot
                break
        if not bot:
            return None

        if not (interface := get_interface(bot)):
            return None

        if not (
            scene := await interface.get_scene(
                SceneType(scene_model.scene_type), scene_model.scene_id, parent_scene_id=parent_scene_id
            )
        ):
            return None

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
        .where(BotModel.adapter == basic_info["adapter"])
    )
    async with get_session() as db_session:
        if bot_model := (await db_session.scalars(statement)).one_or_none():
            bot_model.scope = basic_info["scope"]
            await db_session.commit()
            return bot_model.id

    bot_model = BotModel(
        self_id=basic_info["self_id"],
        adapter=basic_info["adapter"],
        scope=basic_info["scope"],
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

    statement = (
        select(SceneModel)
        .where(SceneModel.bot_persist_id == bot_persist_id)
        .where(SceneModel.scene_id == scene.id)
        .where(SceneModel.scene_type == scene.type)
    )
    async with get_session() as db_session:
        if scene_model := (await db_session.scalars(statement)).one_or_none():
            scene_model.parent_scene_persist_id = parent_scene_persist_id
            scene_model.scene_data = scene.dump()
            await db_session.commit()
            return scene_model.id

    scene_model = SceneModel(
        bot_persist_id=bot_persist_id,
        parent_scene_persist_id=parent_scene_persist_id,
        scene_id=scene.id,
        scene_type=scene.type,
        scene_data=scene.dump(),
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

    statement = select(UserModel).where(UserModel.bot_persist_id == bot_persist_id).where(UserModel.user_id == user.id)
    async with get_session() as db_session:
        if user_model := (await db_session.scalars(statement)).one_or_none():
            user_model.user_data = user.dump()
            await db_session.commit()
            return user_model.id

    user_model = UserModel(
        bot_persist_id=bot_persist_id,
        user_id=user.id,
        user_data=user.dump(),
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
    member_data = session.member.dump() if session.member else None

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


async def get_session_model(persist_id: int) -> SessionModel:
    async with get_session() as db_session:
        return (await db_session.scalars(select(SessionModel).where(SessionModel.id == persist_id))).one()


async def get_session_orm(session: Session = UniSession()):
    return await get_session_model(await get_session_persist_id(session))


def SessionOrm() -> SessionModel:
    return Depends(get_session_orm)
