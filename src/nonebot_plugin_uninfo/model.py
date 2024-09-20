from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Optional, Union

from .constraint import SupportAdapter, SupportScope


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


@dataclass
class Scene:
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


@dataclass
class User:
    id: str
    name: Optional[str] = None
    """用户名"""
    nick: Optional[str] = None
    """用户昵称"""
    avatar: Optional[str] = None
    gender: str = "unknown"


@dataclass
class Role:
    id: str
    level: int = 0
    name: Optional[str] = None


@dataclass
class MuteInfo:
    muted: bool
    """是否被禁言"""
    duration: timedelta
    """禁言时长"""
    start_at: Optional[datetime] = None
    """禁言开始时间"""

    def __post_init__(self):
        if self.duration.total_seconds() < 1:
            self.muted = False


@dataclass
class Member:
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


@dataclass
class Session:
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
