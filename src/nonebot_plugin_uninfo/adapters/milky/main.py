from datetime import datetime
from typing import Optional, Union

from nonebot.adapters.milky import Bot
from nonebot.adapters.milky.event import (
    FriendMessageEvent,
    FriendNudgeEvent,
    FriendRequestEvent,
    GroupInvitationEvent,
    GroupMemberDecreaseEvent,
    GroupMemberIncreaseEvent,
    GroupMessageEvent,
    GroupMuteEvent,
    GroupNudgeEvent,
    GroupRequestEvent,
    MessageEvent,
    MessageRecallEvent,
    TempMessageEvent,
)
from nonebot.adapters.milky.event import Event as MilkyEvent
from nonebot.exception import ActionFailed
from nonebot.internal.adapter import Event

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Role, Scene, SceneType, User

ROLES = {
    "owner": ("OWNER", 100),
    "admin": ("ADMINISTRATOR", 10),
    "member": ("MEMBER", 1),
}


class InfoFetcher(BaseInfoFetcher):
    def get_session_id(self, event: Event) -> str:
        if isinstance(event, GroupNudgeEvent):
            return f"{event.get_session_id()}_{event.data.receiver_id}"
        return event.get_session_id()

    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data.get("name"),
            nick=data.get("nickname"),
            avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['user_id']}&s=640",
            gender=data.get("gender", "unknown"),
        )

    def extract_scene(self, data):
        if "group_id" not in data:
            return Scene(
                id=data["user_id"],
                type=SceneType.PRIVATE,
                name=data.get("name"),
                avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['user_id']}&s=640",
            )
        return Scene(
            id=data["group_id"],
            type=SceneType.GROUP,
            name=data.get("group_name"),
            avatar=f"https://p.qlogo.cn/gh/{data['group_id']}/{data['group_id']}/",
        )

    def extract_member(self, data, user: Optional[User]):
        if "group_id" not in data:
            return None
        if user:
            return Member(
                user=user,
                nick=data.get("card"),
                role=(
                    Role(*ROLES[_role], name=_role)
                    if (_role := data.get("role"))
                    else Role(*ROLES["member"], name="member")
                ),
                joined_at=datetime.fromtimestamp(data["join_time"]) if data.get("join_time") else None,
            )
        return Member(
            User(
                id=data["user_id"],
                name=data.get("name"),
                nick=data.get("nickname"),
                avatar=f"https://q2.qlogo.cn/headimg_dl?dst_uin={data['user_id']}&spec=640",
            ),
            nick=data.get("card"),
            role=(
                Role(*ROLES[_role], name=_role)
                if (_role := data.get("role"))
                else Role(*ROLES["member"], name="member")
            ),
            joined_at=datetime.fromtimestamp(data["join_time"]) if data.get("join_time") else None,
        )

    async def query_user(self, bot: Bot, user_id: str) -> User:
        info = await bot.get_user_profile(user_id=int(user_id))
        data = {
            "user_id": user_id,
            "name": info.nickname,
            "nickname": info.remark,
            "gender": info.sex,
        }
        return self.extract_user(data)

    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type == SceneType.PRIVATE:
            if user := (await self.query_user(bot, scene_id)):
                data = {
                    "user_id": user.id,
                    "name": user.name,
                    "avatar": user.avatar,
                }
                return self.extract_scene(data)

        elif scene_type == SceneType.GROUP:
            group = await bot.get_group_info(group_id=int(scene_id))
            data = {"group_id": group.group_id, "group_name": group.name}
            return self.extract_scene(data)

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        if scene_type != SceneType.GROUP:
            return
        group_id = parent_scene_id

        member = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        data = {
            "group_id": group_id,
            "user_id": str(member.user_id),
            "name": member.nickname,
            "card": member.card,
            "role": member.role,
            "join_time": member.join_time,
            "gender": member.sex,
        }
        return self.extract_member(data, None)

    async def query_users(self, bot: Bot):
        friends = await bot.get_friend_list()
        for friend in friends:
            data = {
                "user_id": str(friend.user_id),
                "name": friend.nickname,
                "nickname": friend.remark,
                "gender": friend.sex,
            }
            yield self.extract_user(data)

    async def query_scenes(
        self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type is None or scene_type == SceneType.PRIVATE:
            async for user in self.query_users(bot):
                data = {
                    "user_id": user.id,
                    "name": user.name,
                    "avatar": user.avatar,
                }
                yield self.extract_scene(data)

        if scene_type is None or scene_type == SceneType.GROUP:
            groups = await bot.get_group_list()
            for group in groups:
                data = {
                    "group_id": str(group.group_id),
                    "group_name": group.name,
                }
                yield self.extract_scene(data)

    async def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        if scene_type != SceneType.GROUP:
            return
        group_id = parent_scene_id

        members = await bot.get_group_member_list(group_id=int(group_id))
        for member in members:
            data = {
                "group_id": group_id,
                "user_id": str(member.user_id),
                "name": member.nickname,
                "card": member.card,
                "role": member.role,
                "join_time": member.join_time,
                "gender": member.sex,
            }
            yield self.extract_member(data, None)

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.milky,
            "scope": SupportScope.qq_client,
        }


fetcher = InfoFetcher(SupportAdapter.milky)


@fetcher.supply
async def _(bot: Bot, event: Union[MessageEvent, GroupMessageEvent, FriendMessageEvent, TempMessageEvent]):
    if event.data.message_scene == "friend":
        assert event.data.friend
        return {
            "user_id": str(event.data.sender_id),
            "name": event.data.friend.nickname,
            "nickname": event.data.friend.remark,
            "gender": event.data.friend.sex,
        }
    assert event.data.group
    if event.data.message_scene == "temp":
        try:
            info = await bot.get_group_member_info(group_id=event.data.group.group_id, user_id=event.data.sender_id)
            base = {
                "user_id": str(event.data.sender_id),
                "name": info.nickname,
                "nickname": info.card,
                "gender": info.sex,
                "role": info.role,
                "join_time": info.join_time,
            }
        except ActionFailed:
            base = {"user_id": str(event.data.sender_id)}
    else:
        assert event.data.group_member
        base = {
            "user_id": str(event.data.sender_id),
            "name": event.data.group_member.nickname,
            "nickname": event.data.group_member.card,
            "gender": event.data.group_member.sex,
            "role": event.data.group_member.role,
            "join_time": event.data.group_member.join_time,
        }
    base |= {
        "group_id": str(event.data.group.group_id),
        "group_name": event.data.group.name,
    }
    return base


@fetcher.supply
async def _(bot: Bot, event: MessageRecallEvent):
    if event.data.message_scene == "friend":
        try:
            info = await bot.get_friend_info(user_id=event.data.sender_id)
            return {
                "user_id": str(event.data.sender_id),
                "name": info.nickname,
                "nickname": info.remark,
                "gender": info.sex,
            }
        except ActionFailed:
            return {"user_id": str(event.data.sender_id)}
    try:
        info = await bot.get_group_member_info(group_id=event.data.peer_id, user_id=event.data.sender_id)
        base = {
            "user_id": str(event.data.sender_id),
            "name": info.nickname,
            "nickname": info.card,
            "gender": info.sex,
            "role": info.role,
            "join_time": info.join_time,
        }
    except ActionFailed:
        base = {"user_id": str(event.data.sender_id)}
    try:
        info = await bot.get_group_info(group_id=event.data.peer_id)
        base |= {
            "group_id": str(event.data.peer_id),
            "group_name": info.name,
        }
    except ActionFailed:
        base["group_id"] = str(event.data.peer_id)
    return base


@fetcher.supply
async def _(bot: Bot, event: FriendNudgeEvent):
    try:
        info = await bot.get_friend_info(user_id=event.data.user_id)
        return {
            "user_id": str(event.data.user_id),
            "name": info.nickname,
            "nickname": info.remark,
            "gender": info.sex,
        }
    except ActionFailed:
        return {"user_id": str(event.data.user_id)}


@fetcher.supply
async def _(bot: Bot, event: GroupNudgeEvent):
    try:
        user = await bot.get_group_member_info(group_id=event.data.group_id, user_id=event.data.receiver_id)
        base: dict = {
            "user_id": str(event.data.receiver_id),
            "name": user.nickname,
            "nickname": user.card,
            "gender": user.sex,
            "role": user.role,
            "join_time": user.join_time,
        }
    except ActionFailed:
        base = {"user_id": str(event.data.receiver_id)}
    try:
        group = await bot.get_group_info(group_id=event.data.group_id)
        base |= {
            "group_id": str(event.data.group_id),
            "group_name": group.name,
        }
    except ActionFailed:
        base["group_id"] = str(event.data.group_id)
    try:
        operator = await bot.get_group_member_info(group_id=event.data.group_id, user_id=event.data.sender_id)
        base["operator"] = {
            "user_id": str(event.data.sender_id),
            "name": operator.nickname,
            "nickname": operator.card,
            "gender": operator.sex,
            "role": operator.role,
            "join_time": operator.join_time,
        }
    except ActionFailed:
        base["operator"] = {"user_id": str(event.data.sender_id)}
    return base


@fetcher.supply
async def _(bot: Bot, event: FriendRequestEvent):
    try:
        info = await bot.get_user_profile(user_id=event.data.initiator_id)
        return {
            "user_id": str(event.data.initiator_id),
            "name": info.nickname,
            "nickname": info.remark,
            "gender": info.sex,
        }
    except ActionFailed:
        return {"user_id": str(event.data.initiator_id)}


@fetcher.supply
async def _(bot: Bot, event: GroupRequestEvent):
    try:
        user = await bot.get_user_profile(user_id=event.data.initiator_id)
        base: dict = {
            "user_id": str(event.data.initiator_id),
            "name": user.nickname,
            "nickname": user.remark,
            "gender": user.sex,
        }
    except ActionFailed:
        base = {"user_id": str(event.data.initiator_id)}
    try:
        group = await bot.get_group_info(group_id=event.data.group_id)
        base |= {
            "group_id": str(event.data.group_id),
            "group_name": group.name,
        }
    except ActionFailed:
        base["group_id"] = str(event.data.group_id)
    if event.data.operator_id:
        try:
            operator = await bot.get_group_member_info(group_id=event.data.group_id, user_id=event.data.operator_id)
            base["operator"] = {
                "user_id": str(event.data.operator_id),
                "name": operator.nickname,
                "nickname": operator.card,
                "gender": operator.sex,
            }
        except ActionFailed:
            base["operator"] = {"user_id": str(event.data.operator_id)}
    return base


@fetcher.supply
async def _(bot: Bot, event: GroupInvitationEvent):
    try:
        user = await bot.get_user_profile(user_id=event.data.initiator_id)
        base = {
            "user_id": str(event.data.initiator_id),
            "name": user.nickname,
            "nickname": user.remark,
            "gender": user.sex,
        }
    except ActionFailed:
        base = {"user_id": str(event.data.initiator_id)}
    try:
        group = await bot.get_group_info(group_id=event.data.group_id)
        base |= {
            "group_id": str(event.data.group_id),
            "group_name": group.name,
        }
    except ActionFailed:
        base["group_id"] = str(event.data.group_id)
    return base


@fetcher.supply
async def _(bot: Bot, event: Union[GroupMemberIncreaseEvent, GroupMemberDecreaseEvent, GroupMuteEvent]):
    try:
        user = await bot.get_group_member_info(group_id=event.data.group_id, user_id=event.data.user_id)
        base: dict = {
            "user_id": str(event.data.user_id),
            "name": user.nickname,
            "nickname": user.card,
            "gender": user.sex,
            "role": user.role,
            "join_time": user.join_time,
        }
    except ActionFailed:
        try:
            user = await bot.get_user_profile(user_id=event.data.user_id)
            base = {
                "user_id": str(event.data.user_id),
                "name": user.nickname,
                "nickname": user.remark,
                "gender": user.sex,
                "role": "member",
            }
        except ActionFailed:
            base = {"user_id": str(event.data.user_id)}
    try:
        group = await bot.get_group_info(group_id=event.data.group_id)
        base |= {
            "group_id": str(event.data.group_id),
            "group_name": group.name,
        }
    except ActionFailed:
        base["group_id"] = str(event.data.group_id)
    if event.data.operator_id:
        try:
            operator = await bot.get_group_member_info(group_id=event.data.group_id, user_id=event.data.operator_id)
            base["operator"] = {
                "user_id": str(event.data.operator_id),
                "name": operator.nickname,
                "nickname": operator.card,
                "gender": operator.sex,
                "role": operator.role,
                "join_time": operator.join_time,
            }
        except ActionFailed:
            base["operator"] = {"user_id": str(event.data.operator_id)}
    return base


@fetcher.supply_wildcard
async def _(bot: Bot, evnet: MilkyEvent):
    try:
        user_id = evnet.get_user_id()
    except ValueError:
        user_id = None
    if evnet.is_private:
        assert user_id
        friend = await bot.get_friend_info(user_id=int(user_id))
        return {
            "user_id": str(user_id),
            "name": friend.nickname,
            "nickname": friend.remark,
            "gender": friend.sex,
        }
    group_id = getattr(evnet.data, "group_id", None)
    if not group_id:
        raise NotImplementedError(evnet)
    if not user_id:
        info = await bot.get_login_info()
        base = {
            "user_id": str(info.uin),
            "name": info.nickname,
        }
    else:
        info = await bot.get_group_member_info(group_id=int(group_id), user_id=int(user_id))
        base = {
            "user_id": user_id,
            "name": info.nickname,
            "nickname": info.card,
            "gender": info.sex,
            "role": info.role,
            "join_time": info.join_time,
        }
    group = await bot.get_group_info(group_id=int(group_id))
    base |= {
        "group_id": str(group.group_id),
        "group_name": group.name,
    }
    return base
