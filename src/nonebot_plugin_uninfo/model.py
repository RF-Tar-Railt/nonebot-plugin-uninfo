from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import IntEnum
import json
from typing import Optional, TypedDict, Union
from typing_extensions import Required, Self

from nonebot.compat import custom_validation

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


class ModelMixin:

    @classmethod
    def load(cls, data: dict):
        return cls(**data)  # type: ignore  # noqa

    def dump(self):
        return asdict(self)  # type: ignore  # noqa

    def dump_json(self):
        return json.dumps(self.dump(), cls=DatetimeJsonEncoder)


@dataclass
class Scene(ModelMixin):
    id: str
    type: SceneType
    name: Optional[str] = None
    avatar: Optional[str] = None
    parent: Optional["Scene"] = None

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
        data["type"] = SceneType(data["type"])
        if data.get("parent"):
            data["parent"] = cls.load(data["parent"])
        return cls(**data)


@dataclass
class User(ModelMixin):
    id: str
    name: Optional[str] = None
    """用户名"""
    nick: Optional[str] = None
    """用户昵称"""
    avatar: Optional[str] = None
    gender: str = "unknown"


@dataclass
class Role(ModelMixin):
    id: str
    level: int = 0
    name: Optional[str] = None


@dataclass
class MuteInfo(ModelMixin):
    muted: bool
    """是否被禁言"""
    duration: timedelta
    """禁言时长"""
    start_at: Optional[datetime] = None
    """禁言开始时间"""

    @classmethod
    def load(cls, data: dict):
        data["duration"] = timedelta(seconds=data["duration"])
        if data.get("start_at"):
            data["start_at"] = datetime.fromtimestamp(data["start_at"])
        return cls(**data)

    def __post_init__(self):
        if self.duration.total_seconds() < 1:
            self.muted = False
        if self.start_at and (datetime.now() - self.start_at) > self.duration:
            self.muted = False


@dataclass
class Member(ModelMixin):
    user: User
    nick: Optional[str] = None
    """群员昵称"""
    role: Optional[Role] = None
    """群员角色"""
    mute: Optional[MuteInfo] = None
    joined_at: Optional[datetime] = None

    @property
    def id(self) -> str:
        return self.user.id

    @classmethod
    def load(cls, data: dict):
        data["user"] = User.load(data["user"])
        if data.get("role"):
            data["role"] = Role.load(data["role"])
        if data.get("mute"):
            data["mute"] = MuteInfo.load(data["mute"])
        if data.get("joined_at"):
            data["joined_at"] = datetime.fromtimestamp(data["joined_at"])
        return cls(**data)


@custom_validation
@dataclass
class Session(ModelMixin):
    self_id: str
    """机器人id"""
    adapter: Union[str, SupportAdapter]
    """适配器名称"""
    scope: Union[str, SupportScope]
    """适配器范围，相比 adapter 更指向实际平台"""
    scene: Scene
    """场景信息"""
    user: User
    member: Optional[Member] = None
    operator: Optional[Member] = None

    platform: Union[str, set[str], None] = None
    """平台名称，仅当目标适配器存在多个平台时使用"""

    @property
    def id(self) -> str:
        if self.scene.is_private:
            return self.scene_path
        return f"{self.scene_path}_{self.user.id}"

    @property
    def scene_path(self) -> str:
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
        if self.scene.is_guild:
            return self.scene
        elif self.scene.is_channel:
            return self.scene.parent

    @property
    def channel(self) -> Optional[Scene]:
        if self.scene.is_channel:
            return self.scene

    @property
    def group(self) -> Optional[Scene]:
        if self.scene.is_group:
            return self.scene

    @property
    def friend(self) -> Optional[Scene]:
        if self.scene.is_private:
            return self.scene

    @property
    def basic(self) -> BasicInfo:
        return {"self_id": self.self_id, "adapter": SupportAdapter(self.adapter), "scope": SupportScope(self.scope)}

    @classmethod
    def load(cls, data: dict):
        data["adapter"] = SupportAdapter(data["adapter"])
        data["scope"] = SupportScope(data["scope"])
        data["scene"] = Scene.load(data["scene"])
        data["user"] = User.load(data["user"])
        if data.get("member"):
            data["member"] = Member.load(data["member"])
        if data.get("operator"):
            data["operator"] = Member.load(data["operator"])
        return cls(**data)

    @classmethod
    def __get_validators__(cls):
        yield cls._validate

    @classmethod
    def _validate(cls, value) -> Self:
        if isinstance(value, cls):
            return value
        raise ValueError(f"Type {type(value)} can not be converted to {cls}")
