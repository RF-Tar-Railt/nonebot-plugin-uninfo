from typing import TYPE_CHECKING, Union, overload

from .model import BasicInfo, Member, Scene, Session, User

if TYPE_CHECKING:
    from nonebot_plugin_alconna import Target


@overload
def to_target(model: Session) -> "Target": ...


@overload
def to_target(model: Union[User, Member, Scene], info: BasicInfo) -> "Target": ...


def to_target(model: Union[Session, User, Member, Scene], info: Union[BasicInfo, None] = None) -> "Target":
    try:
        from nonebot_plugin_alconna import SupportAdapter as AlconnaSupportAdapter
        from nonebot_plugin_alconna import SupportScope as AlconnaSupportScope
        from nonebot_plugin_alconna import Target
    except ImportError:
        raise RuntimeError("Please install nonebot-plugin-alconna to use this function")
    if isinstance(model, Session):
        scene_id = model.scene.id
        scene_parent_id = model.scene.parent.id if model.scene.parent else ""
        return Target(
            scene_id,
            scene_parent_id,
            model.scene.is_private,
            model.scene.is_channel,
            self_id=model.self_id,
            adapter=AlconnaSupportAdapter(model.adapter),
            scope=AlconnaSupportScope(model.scope),
        )
    if not info:
        raise ValueError("info is required when model is not Session")
    if isinstance(model, User):
        return Target(
            model.id,
            private=True,
            self_id=info["self_id"],
            adapter=AlconnaSupportAdapter(info["adapter"]),
            scope=AlconnaSupportScope(info["scope"]),
        )
    elif isinstance(model, Member):
        return Target(
            model.user.id,
            private=True,
            self_id=info["self_id"],
            adapter=AlconnaSupportAdapter(info["adapter"]),
            scope=AlconnaSupportScope(info["scope"]),
        )
    elif isinstance(model, Scene):
        scene_id = model.id
        scene_parent_id = model.parent.id if model.parent else ""
        return Target(
            scene_id,
            scene_parent_id,
            model.is_private,
            model.is_channel,
            self_id=info["self_id"],
            adapter=AlconnaSupportAdapter(info["adapter"]),
            scope=AlconnaSupportScope(info["scope"]),
        )
    else:
        raise ValueError("model must be Session, User, Member or Scene")
