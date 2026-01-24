from typing import Any

from nonebot.adapters.yunhu import Bot
from nonebot.adapters.yunhu.event import (
    PrivateMessageEvent,
    GroupMessageEvent,
    InstructionMessageEvent,
    GroupJoinNoticeEvent,
    GroupLeaveNoticeEvent,
    BotFollowedNoticeEvent,
    BotUnfollowedNoticeEvent,
    TipNoticeEvent,
    ButtonReportNoticeEvent,
)

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Role, Scene, SceneType, User
from nonebot.compat import model_dump
from nonebot.exception import ActionFailed

ROLES = {
    "owner": ("OWNER", 100),
    "administrator": ("ADMINISTRATOR", 10),
    "member": ("MEMBER", 1),
    "unknown": ("UNKNOWN", 0),
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["userId"],
            name=data["nickname"],
            avatar=data["avatarUrl"],
        )

    def extract_scene(self, data):
        if "groupId" in data and data["groupId"]:
            return Scene(
                id=data["groupId"],
                type=SceneType.GROUP,
                name=data["name"],
                avatar=data["groupAvatarUrl"] if "groupAvatarUrl" in data else data["avatarUrl"],
            )
        return Scene(id=data["userId"], type=SceneType.PRIVATE, name=data["nickname"], avatar=data["avatarUrl"])

    def extract_member(self, data: dict[str, Any], user: User | None) -> Member | None:
        if user:
            return Member(user, role=Role(*ROLES[data["role"]], data["role"]) if "role" in data else None)
        return Member(
            self.extract_user(data), role=Role(*ROLES[data["role"]], data["role"]) if "role" in data else None
        )

    async def query_user(self, bot: Bot, user_id: str):
        data = await bot.get_user_info(user_id=user_id)
        if data.data:
            return self.extract_user(model_dump(data.data.user))

    async def query_scene(self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: str | None = None):
        if scene_type == SceneType.PRIVATE:
            if user := await self.query_user(bot, scene_id):
                data = {
                    "userId": user.id,
                    "nickname": user.name,
                    "avatarUrl": user.avatar,
                }
                return self.extract_scene(data)
        elif scene_type == SceneType.GROUP:
            chat = await bot.get_group_info(scene_id)
            if chat.data:
                return self.extract_scene(model_dump(chat.data.group))

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        if scene_type == SceneType.GROUP:
            member = await bot.get_user_info(user_id)
            if member.data:
                return self.extract_member(model_dump(member.data.user), None)

    def query_users(self, bot: Bot):
        raise NotImplementedError

    def query_scenes(self, bot: Bot, scene_type: SceneType | None = None, *, parent_scene_id: str | None = None):
        raise NotImplementedError

    def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        raise NotImplementedError

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": bot.self_id,
            "adapter": SupportAdapter.yunhu,
            "scope": SupportScope.yunhu,
        }


fetcher = InfoFetcher(SupportAdapter.yunhu)


@fetcher.supply
async def _(bot: Bot, event: PrivateMessageEvent):
    return {
        "userId": event.event.sender.senderId,
        "nickname": event.event.sender.senderNickname,
        "avatarUrl": event.event.sender.senderAvatarUrl,
    }


@fetcher.supply
async def _(bot: Bot, event: GroupMessageEvent):
    try:
        group = await bot.get_group_info(event.event.chat.chatId)
        if g := group.data:
            group_info = {
                "name": g.group.name,
                "groupAvatarUrl": g.group.avatarUrl,
            }
        else:
            group_info = {}
    except ActionFailed:
        group_info = {}
    return {
        "userId": event.event.sender.senderId,
        "nickname": event.event.sender.senderNickname,
        "avatarUrl": event.event.sender.senderAvatarUrl,
        "role": event.event.sender.senderUserLevel,
        "groupId": event.event.chat.chatId,
        "name": group_info.get("name"),
        "groupAvatarUrl": group_info.get("groupAvatarUrl"),
    }


@fetcher.supply
async def _(bot: Bot, event: InstructionMessageEvent):
    try:
        if event.event.chat.chatType == "group":
            group = await bot.get_group_info(event.event.chat.chatId)
            if g := group.data:
                group_info = {
                    "name": g.group.name,
                    "groupAvatarUrl": g.group.avatarUrl,
                    "groupId": event.event.chat.chatId,
                }
            else:
                group_info = {}
        else:
            group_info = {}
    except ActionFailed:
        group_info = {}
    return {
        "userId": event.event.sender.senderId,
        "nickname": event.event.sender.senderNickname,
        "avatarUrl": event.event.sender.senderAvatarUrl,
        "groupId": group_info.get("groupId"),
        "name": group_info.get("name"),
        "groupAvatarUrl": group_info.get("groupAvatarUrl"),
    }


@fetcher.supply
async def _(bot: Bot, event: BotFollowedNoticeEvent | BotUnfollowedNoticeEvent):
    return {
        "userId": event.event.userId,
        "nickname": event.event.nickname,
        "avatarUrl": event.event.avatarUrl,
    }


@fetcher.supply
async def _(bot: Bot, event: GroupJoinNoticeEvent | GroupLeaveNoticeEvent):
    try:
        group = await bot.get_group_info(event.event.chatId)
        if g := group.data:
            group_info = {
                "name": g.group.name,
                "groupAvatarUrl": g.group.avatarUrl,
            }
        else:
            group_info = {}
    except ActionFailed:
        group_info = {}
    return {
        "userId": event.event.userId,
        "nickname": event.event.nickname,
        "avatarUrl": event.event.avatarUrl,
        "groupId": event.event.chatId,
        "name": group_info.get("name"),
        "groupAvatarUrl": group_info.get("groupAvatarUrl"),
    }


@fetcher.supply
async def _(bot: Bot, event: TipNoticeEvent):
    try:
        group = await bot.get_group_info(event.event.chatId)
        if g := group.data:
            group_info = {
                "name": g.group.name,
                "groupAvatarUrl": g.group.avatarUrl,
            }
        else:
            group_info = {}
    except ActionFailed:
        group_info = {}
    return {
        "userId": event.event.userId,
        "nickname": event.event.sender.senderNickname,
        "avatarUrl": event.event.sender.senderAvatarUrl,
        "groupId": event.event.chatId,
        "name": group_info.get("name"),
        "groupAvatarUrl": group_info.get("groupAvatarUrl"),
    }


@fetcher.supply
async def _(bot: Bot, event: ButtonReportNoticeEvent):
    try:
        if event.event.chatType == "group":
            group = await bot.get_group_info(event.event.chatId)
            if g := group.data:
                group_info = {
                    "name": g.group.name,
                    "groupAvatarUrl": g.group.avatarUrl,
                    "groupId": event.event.chatId,
                }
            else:
                group_info = {}
        else:
            group_info = {}
    except ActionFailed:
        group_info = {}
    try:
        user = await bot.get_user_info(event.event.userId)
        if u := user.data:
            user_info = {
                "nickname": u.user.nickname,
                "avatarUrl": u.user.avatarUrl,
            }
        else:
            user_info = {}
    except ActionFailed:
        user_info = {}
    return {
        "userId": event.event.userId,
        "nickname": user_info.get("nickname"),
        "avatarUrl": user_info.get("avatarUrl"),
        "groupId": group_info.get("groupId"),
        "name": group_info.get("name"),
        "groupAvatarUrl": group_info.get("groupAvatarUrl"),
    }
