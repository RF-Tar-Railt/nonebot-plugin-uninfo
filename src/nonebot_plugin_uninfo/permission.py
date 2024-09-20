from typing import Callable

from nonebot.adapters import Bot, Event
from nonebot.permission import Permission

from .params import get_session


async def _private(bot: Bot, event: Event) -> bool:
    sess = await get_session(bot, event)
    if not sess:
        return False
    return sess.scene.is_private


PRIVATE: Permission = Permission(_private)
""" 匹配任意私聊类型事件"""


async def _group(bot: Bot, event: Event) -> bool:
    sess = await get_session(bot, event)
    if not sess:
        return False
    return sess.scene.is_group


GROUP: Permission = Permission(_group)
"""匹配任意群聊类型事件"""


async def _guild(bot: Bot, event: Event) -> bool:
    sess = await get_session(bot, event)
    if not sess:
        return False
    return sess.scene.is_guild or sess.scene.is_channel


GUILD: Permission = Permission(_guild)
"""匹配任意频道消息类型事件"""


def ROLE_IN(role_id: str, *role_ids: str) -> Permission:
    """检查成员是否在指定角色组中"""

    async def _role_in(bot: Bot, event: Event) -> bool:
        sess = await get_session(bot, event)
        if not sess or not sess.member or not sess.member.role:
            return False
        return sess.member.role.id in (role_id, *role_ids)

    return Permission(_role_in)


def ROLE_NOT_IN(role_id: str, *role_ids: str) -> Permission:
    """检查成员是否不在指定角色组中"""

    async def _role_not_in(bot: Bot, event: Event) -> bool:
        sess = await get_session(bot, event)
        if not sess or not sess.member or not sess.member.role:
            return True
        return sess.member.role.id not in (role_id, *role_ids)

    return Permission(_role_not_in)


def MEMBER() -> Permission:
    return ROLE_NOT_IN("CHANNEL_ADMINISTRATOR", "ADMINISTRATOR", "OWNER")


def ADMIN() -> Permission:
    return ROLE_IN("ADMINISTRATOR", "OWNER")


def OWNER() -> Permission:
    return ROLE_IN("OWNER")


def ROLE_LEVEL(checker: Callable[[int], bool]) -> Permission:
    """检查用户角色等级"""

    async def _level(bot: Bot, event: Event) -> bool:
        sess = await get_session(bot, event)
        if not sess or not sess.member or not sess.member.role:
            return False
        return checker(sess.member.role.level)

    return Permission(_level)


def USER_IN(user_id: str, *user_ids: str) -> Permission:
    """检查用户是否在指定用户中"""

    async def _user_in(bot: Bot, event: Event) -> bool:
        sess = await get_session(bot, event)
        if not sess:
            return False
        return sess.user.id in (user_id, *user_ids)

    return Permission(_user_in)


def USER_NOT_IN(user_id: str, *user_ids: str) -> Permission:
    """检查用户是否不在指定用户中"""

    async def _user_not_in(bot: Bot, event: Event) -> bool:
        sess = await get_session(bot, event)
        if not sess:
            return True
        return sess.user.id not in (user_id, *user_ids)

    return Permission(_user_not_in)


def SCENE_IN(scene_id: str, *scene_ids: str) -> Permission:
    """检查场景是否在指定场景中"""

    async def _scene_in(bot: Bot, event: Event) -> bool:
        sess = await get_session(bot, event)
        if not sess:
            return False
        return sess.scene.id in (scene_id, *scene_ids)

    return Permission(_scene_in)


def SCENE_NOT_IN(scene_id: str, *scene_ids: str) -> Permission:
    """检查场景是否不在指定场景中"""

    async def _scene_not_in(bot: Bot, event: Event) -> bool:
        sess = await get_session(bot, event)
        if not sess:
            return True
        return sess.scene.id not in (scene_id, *scene_ids)

    return Permission(_scene_not_in)


__all__ = [
    "PRIVATE",
    "GUILD",
    "GROUP",
    "ROLE_IN",
    "ROLE_NOT_IN",
    "MEMBER",
    "ADMIN",
    "OWNER",
    "USER_IN",
    "USER_NOT_IN",
    "SCENE_IN",
    "SCENE_NOT_IN",
    "ROLE_LEVEL",
]
