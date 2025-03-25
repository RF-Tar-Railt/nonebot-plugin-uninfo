from typing import Optional

from nonebot.adapters.gewechat import Bot
from nonebot.adapters.gewechat.event import (
    FriendInfoChangeEvent,
    FriendRemovedEvent,
    FriendRequestEvent,
    MessageEvent,
    NoticeEvent,
    PokeEvent,
    RevokeEvent,
)
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
GENDER = {
    0: "male",
    1: "female",
}


class InfoFetcher(BaseInfoFetcher):
    def get_session_id(self, event: Event) -> str:
        if isinstance(event, PokeEvent):
            return f"poke_{event.FromUserName}_{event.UserId}_{event.ToUserName}"
        if isinstance(event, NoticeEvent):
            return f"{event.FromUserName}_{event.ToUserName or ''}"
        return event.get_session_id()

    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            nick=data.get("remark"),
            avatar=data.get("avatar"),
            gender=GENDER.get(data.get("gender", -1), "unknown"),
        )

    def extract_scene(self, data):
        if "room_id" not in data:
            return Scene(
                id=data["user_id"],
                type=SceneType.PRIVATE,
                name=data["name"],
                avatar=data.get("avatar"),
            )
        return Scene(
            id=data["room_id"],
            type=SceneType.GROUP,
            name=data["room_name"],
            avatar=data.get("room_avatar"),
        )

    def extract_member(self, data, user: Optional[User]):
        if "room_id" not in data:
            return None
        _role = data.get("role", "member")
        if user:
            return Member(
                user=user,
                nick=data["member_name"],
                role=Role(*ROLES[_role], name=_role),
            )
        return Member(
            User(
                id=data["user_id"],
                name=data["name"],
                nick=data["remark"],
                avatar=data.get("avatar"),
                gender=GENDER.get(data.get("gender", -1), "unknown"),
            ),
            nick=data["member_name"],
            role=Role(*ROLES[_role], name=_role),
        )

    async def query_user(self, bot: Bot, user_id: str) -> Optional[User]:
        user_info = (await bot.getBreifInfo([user_id])).data[0]
        return self.extract_user(
            {
                "user_id": user_info.userName,
                "name": user_info.nickName,
                "remark": user_info.remark,
                "gender": user_info.sex,
                "avatar": user_info.bigHeadImgUrl,
            }
        )

    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ) -> Optional[Scene]:
        if scene_type == SceneType.PRIVATE:
            if user := (await self.query_user(bot, scene_id)):
                return self.extract_scene({"user_id": user.id, "name": user.name, "avatar": user.avatar})

        elif scene_type == SceneType.GROUP:
            room_info = (await bot.getChatroomInfo(scene_id)).data
            return self.extract_scene(
                {
                    "room_id": room_info.chatroomId,
                    "room_name": room_info.nickName,
                    "room_avatar": str(room_info.smallHeadImgUrl),
                }
            )

    async def query_member(
        self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str
    ) -> Optional[Member]:
        if scene_type != SceneType.GROUP:
            return
        room_id = parent_scene_id
        room_info = (await bot.getChatroomInfo(room_id)).data
        member_info = (await bot.getChatroomMemberDetail(room_id, [user_id])).data[0]
        base = {
            "member_name": member_info.nickName,
        }
        admins = [d["string"] for d in (await bot.getChatroomMemberList(room_id)).data.adminWxid or []]
        if room_info.chatRoomOwner == user_id:
            base["role"] = "owner"
        elif user_id in admins:
            base["role"] = "admin"
        return self.extract_member(base, await self.query_user(bot, user_id))

    async def query_users(self, bot: Bot):
        resp = await bot.getPhoneAddressList()
        for info in resp.data:
            yield self.extract_user(
                {
                    "user_id": info.userName,
                    "name": info.nickName,
                    "remark": info.remark,
                    "gender": info.sex,
                    "avatar": info.bigHeadImgUrl,
                }
            )

    async def query_scenes(
        self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type is None or scene_type == SceneType.PRIVATE:
            async for user in self.query_users(bot):
                yield self.extract_scene(
                    {
                        "user_id": user.id,
                        "name": user.name,
                        "avatar": user.avatar,
                    }
                )

    async def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        if scene_type != SceneType.GROUP:
            return
        room_id = parent_scene_id
        resp = await bot.getChatroomMemberList(room_id)
        admins = [d["string"] for d in resp.data.adminWxid or []]
        for member in resp.data.memberList:
            base = {
                "user_id": member.wxid,
                "name": member.nickName,
                "member_name": member.displayName or member.nickName,
                "avatar": member.bigHeadImgUrl,
                "role": (
                    "owner"
                    if member.wxid == resp.data.chatroomOwner
                    else "admin" if member.wxid in admins else "member"
                ),
            }
            yield self.extract_member(base, None)

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.gewechat,
            "scope": SupportScope.wechat,
        }


fetcher = InfoFetcher(SupportAdapter.gewechat)


@fetcher.supply
async def _(bot: Bot, event: MessageEvent):
    user_info = (await bot.getBreifInfo([event.UserId])).data[0]
    base = {
        "user_id": user_info.userName,
        "name": user_info.nickName,
        "remark": user_info.remark,
        "gender": user_info.sex,
        "avatar": user_info.bigHeadImgUrl,
    }
    if event.is_group_message():
        room_info = (await bot.getChatroomInfo(event.FromUserName)).data
        base |= {
            "room_id": room_info.chatroomId,
            "room_name": room_info.nickName,
            "room_avatar": str(room_info.smallHeadImgUrl),
        }
        member_info = (await bot.getChatroomMemberDetail(event.FromUserName, [event.UserId])).data[0]
        base |= {
            "member_name": member_info.nickName,
        }
        admins = [d["string"] for d in (await bot.getChatroomMemberList(event.FromUserName)).data.adminWxid or []]
        if room_info.chatRoomOwner == user_info.userName:
            base["role"] = "owner"
        elif user_info.userName in admins:
            base["role"] = "admin"
    return base


@fetcher.supply
async def _(bot: Bot, event: PokeEvent):
    if event.FromUserName == event.UserId:  # private
        user_info = (await bot.getBreifInfo([event.UserId])).data[0]
        return {
            "user_id": user_info.userName,
            "name": user_info.nickName,
            "remark": user_info.remark,
            "gender": user_info.sex,
            "avatar": user_info.bigHeadImgUrl,
            "operator": {
                "user_id": user_info.userName,
                "name": user_info.nickName,
                "remark": user_info.remark,
                "gender": user_info.sex,
                "avatar": user_info.bigHeadImgUrl,
            },
        }
    user_info, operator_info = (await bot.getBreifInfo([event.ToUserName, event.UserId])).data
    base = {
        "user_id": user_info.userName,
        "name": user_info.nickName,
        "remark": user_info.remark,
        "gender": user_info.sex,
        "avatar": user_info.bigHeadImgUrl,
    }
    room_info = (await bot.getChatroomInfo(event.FromUserName)).data
    base |= {
        "room_id": room_info.chatroomId,
        "room_name": room_info.nickName,
        "room_avatar": str(room_info.smallHeadImgUrl),
    }
    member_info, member_operator_info = (
        await bot.getChatroomMemberDetail(event.FromUserName, [event.ToUserName, event.UserId])
    ).data
    base |= {
        "member_name": member_info.nickName,
        "operator": {
            "user_id": operator_info.userName,
            "name": operator_info.nickName,
            "remark": operator_info.remark,
            "gender": operator_info.sex,
            "avatar": operator_info.bigHeadImgUrl,
            "member_name": member_operator_info.nickName,
        },
    }
    admins = [d["string"] for d in (await bot.getChatroomMemberList(event.FromUserName)).data.adminWxid or []]
    if room_info.chatRoomOwner == user_info.userName:
        base["role"] = "owner"
    elif user_info.userName in admins:
        base["role"] = "admin"
    if room_info.chatRoomOwner == operator_info.userName:
        base["operator"]["role"] = "owner"
    elif operator_info.userName in admins:
        base["operator"]["role"] = "admin"
    return base


@fetcher.supply
async def _(bot: Bot, event: NoticeEvent):
    if isinstance(event, RevokeEvent):  # TODO: ensure for chatroom id
        raise NotImplementedError
    if isinstance(event, (FriendInfoChangeEvent, FriendRemovedEvent)):
        user_info = (await bot.getBreifInfo([event.FromUserName])).data[0]
        return {
            "user_id": user_info.userName,
            "name": user_info.nickName,
            "remark": user_info.remark,
            "gender": user_info.sex,
            "avatar": user_info.bigHeadImgUrl,
        }
    if not event.ToUserName:
        raise NotImplementedError
    user_info = (await bot.getBreifInfo([event.ToUserName])).data[0]
    base = {
        "user_id": user_info.userName,
        "name": user_info.nickName,
        "remark": user_info.remark,
        "gender": user_info.sex,
        "avatar": user_info.bigHeadImgUrl,
    }
    room_info = (await bot.getChatroomInfo(event.FromUserName)).data
    base |= {
        "room_id": room_info.chatroomId,
        "room_name": room_info.nickName,
        "room_avatar": str(room_info.smallHeadImgUrl),
    }
    member_info = (await bot.getChatroomMemberDetail(event.FromUserName, [event.ToUserName])).data[0]
    base |= {
        "member_name": member_info.nickName,
    }
    admins = [d["string"] for d in (await bot.getChatroomMemberList(event.FromUserName)).data.adminWxid or []]
    if room_info.chatRoomOwner == user_info.userName:
        base["role"] = "owner"
    elif user_info.userName in admins:
        base["role"] = "admin"
    return base


@fetcher.supply
async def _(bot: Bot, event: FriendRequestEvent):
    user_info = (await bot.getBreifInfo([event.FromUserName])).data[0]
    return {
        "user_id": user_info.userName,
        "name": user_info.nickName,
        "remark": user_info.remark,
        "gender": user_info.sex,
        "avatar": user_info.bigHeadImgUrl,
    }
