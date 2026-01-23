from typing import Any

from nonebot.adapters.yunhu import Bot
from nonebot.adapters.yunhu.event import (
    GroupMessageEvent,
    PrivateMessageEvent,
)
from nonebot.adapters.yunhu.models import Sender

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Role, Scene, SceneType, User
from nonebot.compat import model_dump

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
        if "userId" in data:
            return Scene(id=data["userId"], type=SceneType.PRIVATE, name=data["nickname"], avatar=data["avatarUrl"])
        return Scene(
            id=data["groupId"],
            name=data["name"],
            type=SceneType.GROUP,
            avatar=data["avatarUrl"],
        )

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
                    "user_id": user.id,
                    "name": user.name,
                    "avatar": user.avatar,
                }
                return self.extract_scene(data)

        elif scene_type == SceneType.GROUP:
            chat = await bot.get_group_info(scene_id)
            if g := chat.data:
                return self.extract_scene(model_dump(g.group))

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


async def _supply_userdata(sender: Sender):
    return {
        "user_id": sender.senderId,
        "name": sender.senderNickname,
        "avatai": sender.senderAvatarUrl,
        "role": sender.senderUserLevel,
    }


@fetcher.supply
async def _(bot: Bot, event: PrivateMessageEvent):
    return await _supply_userdata(event.event.sender)


@fetcher.supply
async def _(bot: Bot, event: GroupMessageEvent):
    return await _supply_userdata(event.event.sender)
