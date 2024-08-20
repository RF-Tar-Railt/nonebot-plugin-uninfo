from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Union, Optional

from nonebot.adapters import Adapter

from.constraint import SupportScope, SupportAdapter


class ChannelType(IntEnum):
    TEXT = 0
    """文本频道"""
    DIRECT = 1
    """私聊频道"""
    CATEGORY = 2
    """分类频道"""
    VOICE = 3
    """语音频道"""


@dataclass
class Guild:
    id: str
    name: Optional[str] = None
    avatar: Optional[str] = None


@dataclass
class Channel:
    id: str
    type: ChannelType
    name: Optional[str] = None
    parent: Optional[Guild] = None


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


@dataclass
class Member:
    id: str
    nick: Optional[str] = None
    """群员昵称"""
    role: Optional[Role] = None
    """群员角色"""
    avatar: Optional[str] = None
    mute: Optional[MuteInfo] = None
    joined_at: Optional[datetime] = None


@dataclass
class Session:
    self_id: str
    """机器人id"""
    adapter: Union[str, type[Adapter], SupportAdapter]
    """适配器名称，若为 None 则需要明确指定 Bot 对象"""
    scope: Union[str, SupportScope]
    """适配器范围，相比 adapter 更指向实际平台"""

    channel: Channel
    user: User
    guild: Optional[Guild] = None
    member: Optional[Member] = None


    platform: Union[str, set[str], None] = None
    """平台名称，仅当目标适配器存在多个平台时使用"""

    @property
    def is_private(self) -> bool:
        return self.channel.type == ChannelType.DIRECT

    @property
    def is_channel(self) -> bool:
        return bool(self.guild) and self.channel.id != self.guild.id


# @dataclass
# class Scene:
#     id: str
#     """目标id；若为群聊则为group_id或者channel_id，若为私聊则为user_id"""
#     parent_id: str
#     """父级id；若为频道则为guild_id，其他情况下可能为空字符串（例如 Feishu 下可作为部门 id）"""
#     channel: bool
#     """是否为频道场景，仅当目标平台符合频道概念时"""
#     private: bool
#     """是否为私聊场景"""
#     self_id: Union[str, None]
#     """机器人id，若为 None 则 Bot 对象会随机选择"""
#     scope: Union[str, SupportScope, None] = None
#     """适配器范围，用于传入内置的特定选择器"""
#     adapter: Union[str, type[Adapter], SupportAdapter, None] = None
#     """适配器名称，若为 None 则需要明确指定 Bot 对象"""
#     platform: Union[str, set[str], None] = None
#     """平台名称，仅当目标适配器存在多个平台时使用"""
#     extra: dict[str, Any] = field(default_factory=dict)
#     """额外信息，用于适配器扩展"""
