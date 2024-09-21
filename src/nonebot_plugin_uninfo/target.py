from typing import TYPE_CHECKING, Literal, Union, overload

from .constraint import SupportScope
from .model import BasicInfo, Member, Scene, Session, User

if TYPE_CHECKING:
    from nonebot_plugin_alconna import Target


@overload
def to_target(model: Session, *, without_self: bool = False) -> "Target": ...


@overload
def to_target(model: Union[User, Member, Scene], info: BasicInfo) -> "Target": ...


@overload
def to_target(
    model: Union[User, Member, Scene], info: Union[str, SupportScope], *, without_self: Literal[True]
) -> "Target": ...


def to_target(
    model: Union[Session, User, Member, Scene],
    info: Union[BasicInfo, str, SupportScope, None] = None,
    without_self: bool = False,
) -> "Target":
    try:
        from nonebot_plugin_alconna import SupportAdapter as AlconnaSupportAdapter
        from nonebot_plugin_alconna import SupportScope as AlconnaSupportScope
        from nonebot_plugin_alconna import Target
    except ImportError:
        raise RuntimeError("Please install nonebot-plugin-alconna to use this function")
    if isinstance(model, Session):
        scene_id = model.scene.id
        scene_parent_id = model.scene.parent.id if model.scene.parent else ""
        if without_self:
            return Target(
                scene_id,
                scene_parent_id,
                model.scene.is_private,
                model.scene.is_channel,
                scope=AlconnaSupportScope(model.scope),
            )
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
    if not without_self and not isinstance(info, dict):
        raise ValueError("info must be BasicInfo when model is not Session and without_self is False")
    if isinstance(info, str):
        basic = {"scope": AlconnaSupportScope(info)}
    else:
        basic = {
            "self_id": info["self_id"],
            "adapter": AlconnaSupportAdapter(info["adapter"]),
            "scope": AlconnaSupportScope(info["scope"]),
        }
    if isinstance(model, User):
        return Target(
            model.id,
            private=True,
            **basic,  # type: ignore
        )
    elif isinstance(model, Member):
        return Target(
            model.user.id,
            private=True,
            **basic,  # type: ignore
        )
    elif isinstance(model, Scene):
        scene_id = model.id
        scene_parent_id = model.parent.id if model.parent else ""
        return Target(
            scene_id,
            scene_parent_id,
            model.is_private,
            model.is_channel,
            **basic,  # type: ignore
        )
    else:
        raise ValueError("model must be Session, User, Member or Scene")
