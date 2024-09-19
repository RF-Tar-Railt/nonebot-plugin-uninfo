from typing import Optional, Union

from nonebot.adapters.telegram import Bot
from nonebot.adapters.telegram.event import (
    ForumTopicEditedMessageEvent,
    ForumTopicMessageEvent,
    GroupEditedMessageEvent,
    GroupMessageEvent,
    LeftChatMemberEvent,
    NewChatMemberEvent,
    PrivateEditedMessageEvent,
    PrivateMessageEvent,
)
from nonebot.adapters.telegram.model import User as TelegramUser
from nonebot.exception import ActionFailed

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.fetch import SuppliedData
from nonebot_plugin_uninfo.model import Member, Role, Scene, SceneType, User

ROLES = {
    "creator": ("OWNER", 100),
    "administrator": ("ADMINISTRATOR", 10),
    "member": ("MEMBER", 1),
    "restricted": ("RESTRICTED", 0),
    "left": ("LEFT", 0),
    "kicked": ("KICKED", 0),
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            nick=data["nickname"],
            avatar=data.get("avatar"),
        )

    def extract_scene(self, data):
        if "chat_id" in data:
            if "thread_id" in data:
                return Scene(
                    id=data["thread_id"],
                    type=SceneType.CHANNEL_TEXT,
                    name=data["chat_name"],
                    parent=Scene(
                        id=data["chat_id"],
                        type=SceneType.GUILD,
                        name=data["chat_name"],
                    ),
                )
            return Scene(
                id=data["chat_id"],
                type=SceneType.GROUP,
                name=data["chat_name"],
            )
        return Scene(
            id=data["user_id"],
            name=data["name"],
            type=SceneType.PRIVATE,
            avatar=data.get("avatar"),
        )

    def extract_member(self, data, user: Optional[User]):
        if "chat_id" not in data:
            return None
        if user:
            return Member(
                user=user,
                nick=data["nickname"],
                role=Role(*ROLES[data["role"]], data["role"]) if "role" in data else None,
            )
        return Member(
            User(
                id=data["user_id"],
                name=data["name"],
                nick=data["nickname"],
                avatar=data.get("avatar"),
            ),
            nick=data["nickname"],
            role=Role(*ROLES[data["role"]], data["role"]) if "role" in data else None,
        )

    async def query_user(self, bot: Bot):
        raise NotImplementedError

    async def query_scene(self, bot: Bot, guild_id: Optional[str]):
        raise NotImplementedError

    async def query_member(self, bot: Bot, guild_id: str):
        raise NotImplementedError

    def supply_self(self, bot: Bot) -> SuppliedData:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.telegram,
            "scope": SupportScope.telegram,
        }


fetcher = InfoFetcher(SupportAdapter.telegram)


async def _supply_userdata(bot: Bot, user: Union[str, TelegramUser]):
    if isinstance(user, TelegramUser):
        res = {
            "user_id": str(user.id),
            "name": user.username or "",
            "nickname": user.first_name + (f" {user.last_name}" if user.last_name else ""),
            "avatar": None,
        }
    else:
        res = {
            "user_id": user,
            "name": "",
            "nickname": "",
            "avatar": None,
        }
    try:
        if isinstance(user, str):
            if user == bot.self_id:
                _user = await bot.get_me()
            else:
                _user = await bot.get_chat(chat_id=int(user))
            res["name"] = _user.username or ""
            nickname = _user.first_name
            if nickname and _user.last_name:
                nickname += f" {_user.last_name}"
            res["nickname"] = nickname or ""
        else:
            _user = user
        profile_photos = await bot.get_user_profile_photos(user_id=_user.id, limit=1)
        if profile_photos.total_count > 0:
            file = await bot.get_file(file_id=profile_photos.photos[0][-1].file_id)
            if file.file_path:
                res["avatar"] = f"https://api.telegram.org/file/bot{bot.bot_config.token}/{file.file_path}"
    except ActionFailed:
        pass
    return res


@fetcher.supply
async def _(bot: Bot, event: Union[PrivateMessageEvent, PrivateEditedMessageEvent]):
    return await _supply_userdata(bot, event.from_)


@fetcher.supply
async def _(bot: Bot, event: Union[GroupMessageEvent, GroupEditedMessageEvent]):
    base = await _supply_userdata(bot, event.from_)
    base["chat_id"] = str(event.chat.id)
    base["chat_name"] = event.chat.title
    try:
        member = await bot.get_chat_member(chat_id=event.chat.id, user_id=event.from_.id)
        base["role"] = member.status
    except ActionFailed:
        pass
    return base


@fetcher.supply
async def _(bot: Bot, event: Union[ForumTopicMessageEvent, ForumTopicEditedMessageEvent]):
    base = await _supply_userdata(bot, event.from_)
    base["chat_id"] = str(event.chat.id)
    base["chat_name"] = event.chat.title
    base["thread_id"] = str(event.message_thread_id)
    try:
        member = await bot.get_chat_member(chat_id=event.chat.id, user_id=event.from_.id)
        base["role"] = member.status
    except ActionFailed:
        pass
    return base


@fetcher.supply
async def _(bot: Bot, event: LeftChatMemberEvent):
    base = await _supply_userdata(bot, event.left_chat_member)
    base["chat_id"] = str(event.chat.id)
    base["chat_name"] = event.chat.title
    try:
        member = await bot.get_chat_member(chat_id=event.chat.id, user_id=event.left_chat_member.id)
        base["role"] = member.status
    except ActionFailed:
        pass
    return base


@fetcher.supply
async def _(bot: Bot, event: NewChatMemberEvent):
    base = await _supply_userdata(bot, event.new_chat_members[0])
    base["chat_id"] = str(event.chat.id)
    base["chat_name"] = event.chat.title
    try:
        member = await bot.get_chat_member(chat_id=event.chat.id, user_id=event.new_chat_members[0].id)
        base["role"] = member.status
    except ActionFailed:
        pass
    return base
