from datetime import datetime, timedelta
from typing import Optional, Union

from nonebot.adapters import Bot
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.model import SceneType, User, Scene, Role, Member, MuteInfo, Session

from nonebot.adapters.mirai import Bot
from nonebot.exception import ActionFailed
from nonebot.adapters.mirai.model.relationship import MemberPerm
from nonebot.adapters.mirai.event import (
    FriendMessage,
    GroupMessage,
    TempMessage,
    StrangerMessage,
)


ROLES = {
    MemberPerm.Owner: Role("OWNER", 100, "OWNER"),
    MemberPerm.Administrator: Role("ADMINISTRATOR", 10, "ADMINISTRATOR"),
    MemberPerm.Member: Role("MEMBER", 1, "MEMBER"),
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(
            id=data["user_id"],
            name=data["name"],
            nick=data.get("nickname"),
            avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['user_id']}&s=640",
            gender=data.get("gender", "unknown"),
        )

    def extract_scene(self, data):
        if "group_id" not in data:
            return Scene(
                id=data["user_id"],
                type=SceneType.PRIVATE,
            )
        return Scene(
            id=data["group_id"],
            type=SceneType.GROUP,
            name=data["group_name"],
            avatar=f"https://p.qlogo.cn/gh/{data['group_id']}/{data['group_id']}/"
        )
    
    def extract_member(self, data, user: Optional[User]):
        if "group_id" not in data:
            return None
        if user:
            return Member(
                user=user,
                nick=data["card"],
                role=ROLES[_role] if (_role := data.get("role")) else None,
                joined_at=datetime.fromtimestamp(data["join_time"]) if data["join_time"] else None,
                mute=MuteInfo(
                    muted=True,
                    duration=timedelta(seconds=data["mute_duration"])
                ) if "mute_duration" in data else None
            )
        return Member(
            User(
                id=data["user_id"],
                name=data["name"],
                nick=data.get("nickname"),
                avatar=f"https://q2.qlogo.cn/headimg_dl?dst_uin={data['user_id']}&spec=640",
            ),
            nick=data["card"],
            role=ROLES[_role] if (_role := data.get("role")) else None,
            joined_at=datetime.fromtimestamp(data["join_time"]) if data["join_time"] else None,
            mute=MuteInfo(
                muted=True,
                duration=timedelta(seconds=data["mute_duration"])
            ) if "mute_duration" in data else None
        )

    async def query_user(self, bot: Bot):
        friends = await bot.get_friend_list()
        for friend in friends:
            data = {
                "user_id": str(friend.id),
                "name": friend.nickname,
                "nickname": friend.remark,
            }
            yield self.extract_user(data)

    async def query_scene(self, bot: Bot, guild_id: Optional[str]):
        groups = await bot.get_group_list()
        for group in groups:
            if not guild_id or str(group.id) == guild_id:
                data = {
                    "group_id": str(group.id),
                    "group_name": group.name,
                }
                yield self.extract_scene(data)

    async def query_member(self, bot: Bot, guild_id: str):
        members = await bot.get_member_list(group=int(guild_id))
        for member in members:
            try:
                info = await bot.get_member_profile(group=int(guild_id), member=member.id)
                data = {
                    "group_id": str(guild_id),
                    "user_id": str(member.id),
                    "name": info.nickname,
                    "card": member.name,
                    "role": member.permission,
                    "join_time": member.join_timestamp,
                    "gender": info.sex.lower(),
                    "mute_duration": member.mute_time
                }
            except ActionFailed:
                data = {
                    "group_id": str(guild_id),
                    "user_id": str(member.id),
                    "name": member.name,
                    "card": member.name,
                    "role": member.permission,
                    "join_time": member.join_timestamp,
                    "mute_duration": member.mute_time
                }
            yield self.extract_member(data, None)

fetcher = InfoFetcher(SupportAdapter.mirai)

@fetcher.supply
async def _(bot: Bot, event: FriendMessage):
    try:
        info = await bot.get_friend_profile(friend=event.sender)
        sex = info.sex.lower()
    except ActionFailed:
        sex = "unknown"
    return {
        "self_id": str(bot.self_id),
        "adapter": SupportAdapter.onebot11,
        "scope": SupportScope.qq_client,
        "user_id": str(event.sender.id),
        "name": event.sender.nickname,
        "nickname": event.sender.remark,
        "gender": sex,
    }

@fetcher.supply
async def _(bot: Bot, event: StrangerMessage):
    try:
        info = await bot.get_user_profile(target=event.sender)
        sex = info.sex.lower()
    except ActionFailed:
        sex = "unknown"
    return {
        "self_id": str(bot.self_id),
        "adapter": SupportAdapter.onebot11,
        "scope": SupportScope.qq_client,
        "user_id": str(event.sender.id),
        "name": event.sender.nickname,
        "nickname": event.sender.remark,
        "gender": sex,
    }

@fetcher.supply
async def _(bot: Bot, event: Union[GroupMessage, TempMessage]):
    try:
        member_info = await bot.get_member_profile(group=event.group.id, member=event.sender.id)
        nickname = member_info.nickname
    except ActionFailed:
        nickname = event.sender.name
    return {
        "self_id": str(bot.self_id),
        "adapter": SupportAdapter.onebot11,
        "scope": SupportScope.qq_client,
        "group_id": str(event.group.id),
        "group_name": event.group.name,
        "user_id": str(event.sender.id),
        "name": nickname,
        "card": event.sender.name,
        "role": event.sender.permission,
        "join_time": event.sender.join_timestamp,
        "mute_duration": event.sender.mute_time
    }
