from datetime import datetime
from typing import Optional

from nonebot.adapters.milky import Bot
from nonebot.adapters.milky.event import GroupNudgeEvent, MessageEvent, MessageRecallEvent
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
        info = await bot.get_friend_info(user_id=int(user_id))
        data = {
            "user_id": user_id,
            "name": info.nickname,
            "nickname": info.remark,
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
async def _(bot: Bot, event: MessageEvent):
    if event.data.message_scene == "friend":
        assert event.data.friend
        return {
            "user_id": str(event.data.sender_id),
            "name": event.data.friend.nickname,
            "nickname": event.data.friend.remark,
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


#
# @fetcher.supply
# async def _(
#     bot: Bot,
#     event: Union[
#         GroupUploadNoticeEvent,
#         GroupAdminNoticeEvent,
#         GroupRequestEvent,
#         HonorNotifyEvent,
#     ],
# ):
#     try:
#         group_info = await bot.get_group_info(group_id=event.group_id)
#     except ActionFailed:
#         group_info = {}
#     try:
#         member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
#     except ActionFailed:
#         member_info = {}
#     return {
#         "group_id": str(event.group_id),
#         "group_name": group_info.get("group_name"),
#         "user_id": str(event.user_id),
#         "name": member_info.get("nickname"),
#         "nickname": member_info.get("card"),
#         "card": member_info.get("card"),
#         "role": member_info.get("role"),
#         "join_time": member_info.get("join_time"),
#         "gender": member_info.get("sex", "unknown"),
#     }
#
#
# @fetcher.supply
# async def _(
#     bot: Bot,
#     event: PokeNotifyEvent,
# ):
#     if not event.group_id:
#         async for friend in fetcher.query_users(bot):
#             if friend.id == str(event.user_id):
#                 friend_info = {
#                     "nickname": friend.name,
#                     "remark": friend.nick,
#                 }
#                 break
#         else:
#             try:
#                 friend_info = await bot.get_stranger_info(user_id=event.user_id)
#             except ActionFailed:
#                 friend_info = {}
#         return {
#             "user_id": str(event.user_id),
#             "name": friend_info.get("nickname"),
#             "nickname": friend_info.get("remark"),
#             "gender": friend_info.get("sex", "unknown"),
#             "operator": {
#                 "user_id": str(event.user_id),
#                 "name": friend_info.get("nickname"),
#                 "nickname": friend_info.get("remark"),
#                 "gender": friend_info.get("sex", "unknown"),
#             },
#         }
#     try:
#         group_info = await bot.get_group_info(group_id=event.group_id)
#     except ActionFailed:
#         group_info = {}
#     try:
#         operator_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
#     except ActionFailed:
#         operator_info = {}
#     try:
#         member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.target_id, no_cache=True)
#     except ActionFailed:
#         member_info = {}
#     return {
#         "group_id": str(event.group_id),
#         "group_name": group_info.get("group_name"),
#         "user_id": str(event.target_id),
#         "name": member_info.get("nickname"),
#         "nickname": member_info.get("card"),
#         "card": member_info.get("card"),
#         "role": member_info.get("role"),
#         "join_time": member_info.get("join_time"),
#         "gender": member_info.get("sex", "unknown"),
#         "operator": {
#             "group_id": str(event.group_id),
#             "user_id": str(event.user_id),
#             "name": operator_info.get("nickname"),
#             "nickname": operator_info.get("card"),
#             "card": operator_info.get("card"),
#             "role": operator_info.get("role"),
#             "join_time": operator_info.get("join_time"),
#             "gender": operator_info.get("sex", "unknown"),
#         },
#     }
#
#
# @fetcher.supply
# async def _(
#     bot: Bot,
#     event: Union[
#         GroupDecreaseNoticeEvent,
#         GroupIncreaseNoticeEvent,
#         GroupRecallNoticeEvent,
#     ],
# ):
#     try:
#         group_info = await bot.get_group_info(group_id=event.group_id)
#     except ActionFailed:
#         group_info = {}
#     try:
#         member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
#     except ActionFailed:
#         member_info = {}
#     try:
#         operator_info = await bot.get_group_member_info(
#             group_id=event.group_id, user_id=event.operator_id, no_cache=True
#         )
#     except ActionFailed:
#         operator_info = {}
#     return {
#         "group_id": str(event.group_id),
#         "group_name": group_info.get("group_name"),
#         "user_id": str(event.user_id),
#         "name": member_info.get("nickname"),
#         "nickname": member_info.get("card"),
#         "card": member_info.get("card"),
#         "role": member_info.get("role"),
#         "join_time": member_info.get("join_time"),
#         "gender": member_info.get("sex", "unknown"),
#         "operator": {
#             "group_id": str(event.group_id),
#             "user_id": str(event.operator_id),
#             "name": operator_info.get("nickname"),
#             "nickname": operator_info.get("card"),
#             "card": operator_info.get("card"),
#             "role": operator_info.get("role"),
#             "join_time": operator_info.get("join_time"),
#             "gender": operator_info.get("sex", "unknown"),
#         },
#     }
#
#
# @fetcher.supply
# async def _(
#     bot: Bot,
#     event: GroupBanNoticeEvent,
# ):
#     try:
#         group_info = await bot.get_group_info(group_id=event.group_id)
#     except ActionFailed:
#         group_info = {}
#     try:
#         member_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id, no_cache=True)
#     except ActionFailed:
#         member_info = {}
#     try:
#         operator_info = await bot.get_group_member_info(
#             group_id=event.group_id, user_id=event.operator_id, no_cache=True
#         )
#     except ActionFailed:
#         operator_info = {}
#     return {
#         "group_id": str(event.group_id),
#         "group_name": group_info.get("group_name"),
#         "user_id": str(event.user_id),
#         "name": member_info.get("nickname"),
#         "nickname": member_info.get("card"),
#         "card": member_info.get("card"),
#         "role": member_info.get("role"),
#         "join_time": member_info.get("join_time"),
#         "gender": member_info.get("sex", "unknown"),
#         "mute_duration": event.duration,
#         "operator": {
#             "group_id": str(event.group_id),
#             "user_id": str(event.operator_id),
#             "name": operator_info.get("nickname"),
#             "nickname": operator_info.get("card"),
#             "card": operator_info.get("card"),
#             "role": operator_info.get("role"),
#             "join_time": operator_info.get("join_time"),
#             "gender": operator_info.get("sex", "unknown"),
#         },
#     }
