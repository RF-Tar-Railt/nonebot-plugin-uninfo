from datetime import datetime

from nonebot.adapters import Bot
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.model import ChannelType, User, Guild, Channel, Role, Member, Session

from nonebot.adapters.onebot.v11 import Bot
from nonebot.exception import ActionFailed
from nonebot.adapters.onebot.v11.event import PrivateMessageEvent, GroupMessageEvent


ROLES = {
    "owner": ("OWNER", 100),
    "admin": ("ADMINISTRATOR", 10),
    "member": ("MEMBER", 1),
}


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        if data["scene_type"] == "group":
            return User(
                id=data["member_id"],
                name=data["name"],
                nick=data["nickname"],
                avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['member_id']}&s=640",
                gender=data.get("gender", "unknown"),
            )
        return User(
            id=data["scene_id"],
            name=data["name"],
            nick=data["nickname"],
            avatar=f"http://q1.qlogo.cn/g?b=qq&nk={data['scene_id']}&s=640",
            gender=data.get("gender", "unknown"),
        )
    
    def extract_channel(self, data):
        if data["scene_type"] == "private":
            return Channel(
                id=data["scene_id"],
                type=ChannelType.DIRECT,
            )
        return Channel(
            id=data["scene_id"],
            type=ChannelType.TEXT,
            name=data["group_name"],
        )
    
    def extract_guild(self, data):
        if data["scene_type"] == "private":
            return None
        return Guild(
            id=data["scene_id"],
            name=data["group_name"],
            avatar=f"https://p.qlogo.cn/gh/{data['scene_id']}/{data['scene_id']}/"
        )
    
    def extract_member(self, data):
        if data["scene_type"] == "private":
            return None
        return Member(
            id=data["member_id"],
            nick=data["nickname"],
            role=Role(*ROLES[_role], name=_role) if (_role := data.get("role")) else None,
            avatar=f"https://q2.qlogo.cn/headimg_dl?dst_uin={data['scene_id']}&spec=640",
            joined_at=datetime.fromtimestamp(data["join_time"]) if data["join_time"] else None
        )

    async def query_user(self, bot: Bot):
        friends = await bot.get_friend_list()
        for friend in friends:
            data = {
                "scene_id": str(friend["user_id"]),
                "name": friend["nickname"],
                "nickname": friend["remark"],
                "scene_type": "private",
            }
            yield self.extract_user(data)

    async def query_channel(self, bot: Bot, guild_id: str):
        groups = await bot.get_group_list()
        for group in groups:
            if group["group_id"] == guild_id:
                data = {
                    "scene_id": str(group["group_id"]),
                    "group_name": group["group_name"],
                    "scene_type": "group",
                }
                yield self.extract_channel(data)

    async def query_guild(self, bot: Bot):
        groups = await bot.get_group_list()
        for group in groups:
            data = {
                "scene_id": str(group["group_id"]),
                "group_name": group["group_name"],
                "scene_type": "group",
            }
            yield self.extract_guild(data)

    async def query_member(self, bot: Bot, guild_id: str):
        members = await bot.get_group_member_list(group_id=int(guild_id))
        for member in members:
            data = {
                "scene_id": str(member["user_id"]),
                "name": member["nickname"],
                "nickname": member["card"],
                "role": member["role"],
                "join_time": member.get("join_time"),
                "gender": member["sex"]
            }
            yield self.extract_member(data)

fetcher = InfoFetcher(SupportAdapter.onebot11)

@fetcher.register(PrivateMessageEvent)
async def _(bot, event: PrivateMessageEvent):
    return {
        "self_id": str(bot.self_id),
        "adapter": SupportAdapter.onebot11,
        "scope": SupportScope.qq_client,
        "scene_id": str(event.user_id),
        "name": event.sender.nickname,
        "nickname": event.sender.card,
        "scene_type": "private",
        "gender": event.sender.sex or "unknown",
    }


@fetcher.register(GroupMessageEvent)
async def _(bot, event: GroupMessageEvent):
    try:
        group_info = await bot.get_group_info(group_id=event.group_id)
    except ActionFailed:
        group_info = {}
    try:
        member_info = await bot.get_group_member_info(
            group_id=event.group_id,
            user_id=event.user_id,
            no_cache=True
        )
    except ActionFailed:
        member_info = {}
    return {
        "self_id": str(bot.self_id),
        "adapter": SupportAdapter.onebot11,
        "scope": SupportScope.qq_client,
        "scene_id": str(event.group_id),
        "group_name": group_info.get("group_name"),
        "scene_type": "group",
        "member_id": str(event.user_id),
        "name": event.sender.nickname,
        "nickname": event.sender.card,
        "role": event.sender.role,
        "join_time": member_info.get("join_time"),
    }
