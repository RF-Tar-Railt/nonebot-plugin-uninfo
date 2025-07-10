from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import IntEnum
import json
from typing import Any, Optional, TypedDict, TypeVar, Union
from typing_extensions import Required

from nonebot.compat import DEFAULT_CONFIG, PYDANTIC_V2

from .constraint import SupportAdapter, SupportScope
from .util import DatetimeJsonEncoder


class BasicInfo(TypedDict):
    self_id: Required[str]
    adapter: Required[SupportAdapter]
    scope: Required[SupportScope]


class SceneType(IntEnum):
    PRIVATE = 0
    """私聊场景"""
    GROUP = 1
    """群聊场景"""
    GUILD = 2
    """频道场景"""
    CHANNEL_TEXT = 3
    """子频道文本场景"""
    CHANNEL_CATEGORY = 4
    """频道分类场景"""
    CHANNEL_VOICE = 5
    """子频道语音场景"""


C = TypeVar("C")


def _apply_schema(cls: type[C]) -> type[C]:
    if PYDANTIC_V2:
        from pydantic import VERSION
        from pydantic._internal._config import ConfigWrapper
        from pydantic._internal._dataclasses import complete_dataclass

        origin_init = cls.__init__
        origin_post_init = getattr(cls, "__post_init__", None)
        if int(VERSION.split(".")[1]) >= 10:
            complete_dataclass(cls, ConfigWrapper(DEFAULT_CONFIG, check=False))  # type: ignore
        else:
            complete_dataclass(cls, ConfigWrapper(DEFAULT_CONFIG, check=False), types_namespace=None)  # type: ignore
        cls.__init__ = origin_init  # type: ignore
        if origin_post_init:
            cls.__post_init__ = origin_post_init  # type: ignore
    else:
        from pydantic.dataclasses import _add_pydantic_validation_attributes

        origin_init = cls.__init__
        origin_post_init = getattr(cls, "__post_init__", None)
        _add_pydantic_validation_attributes(cls, DEFAULT_CONFIG, False, cls.__doc__ or "")
        cls.__init__ = origin_init  # type: ignore
        if origin_post_init:
            cls.__post_init__ = origin_post_init  # type: ignore
        cls.__pydantic_model__.update_forward_refs()
    return cls


class ModelMixin:

    @classmethod
    def load(cls, data: dict):
        return cls(**data)  # type: ignore  # noqa

    def dump(self) -> dict[str, Any]:
        return json.loads(self.dump_json())

    def dump_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=indent, cls=DatetimeJsonEncoder)  # type: ignore  # noqa


class HashableMixin:
    id: str

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self.id == other.id


@_apply_schema
@dataclass
class Scene(ModelMixin, HashableMixin):
    """对话场景，如群组、频道、私聊等"""

    id: str
    """场景id"""
    type: SceneType
    """场景类型"""
    name: Optional[str] = None
    """场景名称"""
    avatar: Optional[str] = None
    """场景头像"""
    parent: Optional["Scene"] = None
    """父级场景"""

    @property
    def is_private(self) -> bool:
        return self.type == SceneType.PRIVATE

    @property
    def is_group(self) -> bool:
        return self.type == SceneType.GROUP

    @property
    def is_guild(self) -> bool:
        return self.type == SceneType.GUILD

    @property
    def is_channel(self) -> bool:
        return self.type.value >= SceneType.CHANNEL_TEXT.value

    @classmethod
    def load(cls, data: dict):
        _data = data.copy()
        _data["type"] = SceneType(data["type"])
        if data.get("parent"):
            _data["parent"] = cls.load(data["parent"])
        return cls(**_data)


@_apply_schema
@dataclass
class User(ModelMixin, HashableMixin):
    """用户信息"""

    id: str
    """用户id"""
    name: Optional[str] = None
    """用户名"""
    nick: Optional[str] = None
    """用户昵称"""
    avatar: Optional[str] = None
    """用户头像"""
    gender: str = "unknown"
    """用户性别"""


@_apply_schema
@dataclass
class Role(ModelMixin):
    """群员角色信息"""

    id: str
    """角色id"""
    level: int = 0
    """角色等级/权限"""
    name: Optional[str] = None
    """角色名称"""


@_apply_schema
@dataclass
class MuteInfo(ModelMixin):
    """禁言信息"""

    muted: bool
    """是否被禁言"""
    duration: timedelta
    """禁言时长"""
    start_at: Optional[datetime] = None
    """禁言开始时间"""

    @classmethod
    def load(cls, data: dict):
        _data = data.copy()
        _data["duration"] = timedelta(seconds=data["duration"])
        if data.get("start_at"):
            _data["start_at"] = datetime.fromtimestamp(data["start_at"])
        return cls(**_data)

    def __post_init__(self):
        if self.duration.total_seconds() < 1:
            self.muted = False
        if self.start_at and (datetime.now() - self.start_at) > self.duration:
            self.muted = False


@_apply_schema
@dataclass
class Member(ModelMixin):
    """群员信息"""

    user: User
    """群员用户信息"""
    nick: Optional[str] = None
    """群员昵称"""
    role: Optional[Role] = None
    """群员角色"""
    mute: Optional[MuteInfo] = None
    """群员禁言信息"""
    joined_at: Optional[datetime] = None
    """加入时间"""

    @property
    def id(self) -> str:
        return self.user.id

    @classmethod
    def load(cls, data: dict):
        _data = data.copy()
        _data["user"] = User.load(data["user"])
        if data.get("role"):
            _data["role"] = Role.load(data["role"])
        if data.get("mute"):
            _data["mute"] = MuteInfo.load(data["mute"])
        if data.get("joined_at"):
            _data["joined_at"] = datetime.fromtimestamp(data["joined_at"])
        return cls(**_data)


@_apply_schema
@dataclass
class Session(ModelMixin, HashableMixin):
    """对话信息"""

    self_id: str
    """机器人id"""
    adapter: Union[str, SupportAdapter]
    """适配器名称"""
    scope: Union[str, SupportScope]
    """适配器范围，相比 adapter 更指向实际平台"""
    scene: Scene
    """场景信息"""
    user: User
    """用户信息"""
    member: Optional[Member] = None
    """群员信息"""
    operator: Optional[Member] = None
    """操作者信息"""
    platform: Union[str, set[str], None] = None
    """平台名称，仅当目标适配器存在多个平台时使用"""

    @property
    def id(self) -> str:
        """会话唯一标识符"""
        if self.scene.is_private:
            return self.scene_path
        return f"{self.scene_path}_{self.user.id}"

    @property
    def scene_path(self) -> str:
        """会话的场景路径，类似于 `event.get_session_id()`"""
        if self.scene.is_private:
            if self.scene.parent:
                return f"{self.scene.parent.id}_{self.user.id}"
            return self.user.id
        if self.scene.is_group:
            return self.scene.id
        if self.scene.parent:
            return f"{self.scene.parent.id}_{self.scene.id}"
        return self.scene.id

    @property
    def guild(self) -> Optional[Scene]:
        """父级频道"""
        if self.scene.is_guild:
            return self.scene
        elif self.scene.is_channel:
            return self.scene.parent

    @property
    def channel(self) -> Optional[Scene]:
        """子频道"""
        if self.scene.is_channel:
            return self.scene

    @property
    def group(self) -> Optional[Scene]:
        """群组"""
        if self.scene.is_group:
            return self.scene

    @property
    def friend(self) -> Optional[Scene]:
        """好友"""
        if self.scene.is_private:
            return self.scene

    @property
    def basic(self) -> BasicInfo:
        return {"self_id": self.self_id, "adapter": SupportAdapter(self.adapter), "scope": SupportScope(self.scope)}

    @classmethod
    def load(cls, data: dict):
        _data = data.copy()
        _data["adapter"] = SupportAdapter(data["adapter"])
        _data["scope"] = SupportScope(data["scope"])
        _data["scene"] = Scene.load(data["scene"])
        _data["user"] = User.load(data["user"])
        if data.get("member"):
            _data["member"] = Member.load(data["member"])
        if data.get("operator"):
            _data["operator"] = Member.load(data["operator"])
        return cls(**_data)
