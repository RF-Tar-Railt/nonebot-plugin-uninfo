from typing import Any, Optional, Union

from nonebot.adapters.feishu import Bot
from nonebot.adapters.feishu.event import GroupMessageEvent, PrivateMessageEvent
from nonebot.exception import ActionFailed

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Role, Scene, SceneType, User


def _handle_gender(gender: int) -> str:
    return "male" if gender == 1 else "female" if gender == 2 else "unknown"


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data: dict[str, Any]) -> User:
        return User(
            id=data["user_id"],
            name=data["name"],
            nick=data.get("nickname"),
            avatar=data.get("avatar"),
            gender=data.get("gender", "unknown"),
        )

    def extract_scene(self, data: dict[str, Any]) -> Scene:
        if "group_id" in data:
            return Scene(
                id=data["group_id"],
                type=SceneType.GROUP,
                name=data.get("group_name"),
                avatar=data.get("group_avatar"),
            )
        return Scene(
            id=data["user_id"],
            type=SceneType.PRIVATE,
            name=data["name"],
            avatar=data.get("avatar"),
        )

    def extract_member(self, data: dict[str, Any], user: Optional[User]):
        if "group_id" not in data:
            return None
        if user:
            return Member(
                user=user,
                nick=data.get("member_name"),
                role=data.get("role", Role("MEMBER", 1, "member")),
            )
        return Member(
            User(
                id=data["user_id"],
                name=data["name"],
                nick=data.get("nickname"),
                avatar=data.get("avatar"),
            ),
            nick=data.get("member_name"),
            role=data.get("role", Role("MEMBER", 1, "member")),
        )

    async def query_user(self, bot: Bot, user_id: str):
        resp = await bot.call_api(
            f"contact/v3/users/{user_id}",
            method="GET",
            query={"user_id_type": "open_id"},
        )
        info = resp["data"]["user"]
        return self.extract_user(
            {
                "user_id": info["open_id"],
                "name": info["name"],
                "nickname": info["nickname"],
                "avatar": info["avatar"]["avatar_origin"],
                "gender": _handle_gender(info["gender"]),
            }
        )

    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ):
        if scene_type == SceneType.PRIVATE:
            if user := await self.query_user(bot, scene_id):
                return self.extract_scene(
                    {
                        "user_id": user.id,
                        "name": user.name,
                        "avatar": user.avatar,
                    }
                )

        elif scene_type == SceneType.GROUP:
            resp = await bot.call_api(
                f"im/v1/chats/{scene_id}",
                method="GET",
            )
            info = resp["data"]
            return self.extract_scene(
                {
                    "group_id": scene_id,
                    "group_name": info["name"],
                    "group_avatar": info["avatar"],
                }
            )

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        raise NotImplementedError

    async def query_users(self, bot: Bot):
        has_more1 = True
        has_more2 = True
        params1 = {}
        params2 = {}
        while has_more1:
            resp1 = await bot.call_api(
                "contact/v3/users/group/simplelist",
                method="GET",
                query=params1,
            )
            params1["page_token"] = resp1["data"]["page_token"]
            has_more1 = resp1["data"]["has_more"]
            for user_group in resp1["data"]["groupList"]:
                while has_more2:
                    resp2 = await bot.call_api(
                        f"contact/v3/users/simplelist/{user_group['id']}/member/simplelist",
                        method="GET",
                        query=params2,
                    )
                    params2["page_token"] = resp2["data"]["page_token"]
                    has_more2 = resp2["data"]["has_more"]
                    for user in resp2["data"]["memberlist"]:
                        member_id = user["user_id"]
                        resp = await bot.call_api(
                            f"contact/v3/users/{member_id}",
                            method="GET",
                            query={"user_id_type": user["member_id_type"]},
                        )
                        info = resp["data"]["user"]
                        gender = _handle_gender(info["gender"])
                        yield self.extract_user(
                            {
                                "user_id": info["open_id"],
                                "name": info["name"],
                                "avatar": info["avatar"]["avatar_origin"],
                                "nickname": info["nickname"],
                                "gender": gender,
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
            if scene_type == SceneType.PRIVATE:
                return

        if scene_type is not None and scene_type != SceneType.GROUP:
            return

        params = {}
        has_more = True
        while has_more:
            resp = await bot.call_api(
                "im/v1/chats/",
                method="GET",
                query=params,
            )
            page_token = resp["data"]["page_token"]
            params["page_token"] = page_token
            has_more = resp["data"]["has_more"]
            for chat in resp["data"]["items"]:
                yield self.extract_scene(
                    {
                        "group_id": chat["chat_id"],
                        "group_name": chat["name"],
                        "group_avatar": chat["avatar"],
                    }
                )

    async def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        if scene_type != SceneType.GROUP:
            return
        group_id = parent_scene_id

        resp = await bot.call_api(
            f"im/v1/chats/{group_id}",
            method="GET",
        )
        owner_id = resp["data"]["owner_id"]
        owner_id_type = resp["data"]["owner_id_type"]
        resp = await bot.call_api(
            f"contact/v3/users/{owner_id}",
            method="GET",
            query={"user_id_type": owner_id_type},
        )
        owner_id = resp["data"]["user"]["open_id"]
        has_more = True
        params = {}
        while has_more:
            resp = await bot.call_api(
                f"im/v1/chats/{group_id}/members",
                method="GET",
                query=params,
            )
            page_token = resp["data"]["page_token"]
            params["page_token"] = page_token
            has_more = resp["data"]["has_more"]
            for member in resp["data"]["items"]:
                resp = await bot.call_api(
                    f"contact/v3/users/{member['member_id']}",
                    method="GET",
                    query={"user_id_type": member["member_id_type"]},
                )
                info = resp["data"]["user"]
                yield self.extract_member(
                    {
                        "user_id": info["open_id"],
                        "name": info["name"],
                        "avatar": info["avatar"]["avatar_origin"],
                        "nickname": info["nickname"],
                        "member_name": member["name"],
                        "group_id": group_id,
                        "role": (
                            Role("OWNER", 100, "owner")
                            if member["open_id"] == owner_id
                            else Role("MEMBER", 1, "member")
                        ),
                    },
                    None,
                )

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.feishu,
            "scope": SupportScope.feishu,
        }


fetcher = InfoFetcher(SupportAdapter.feishu)


@fetcher.supply
async def _(bot: Bot, event: Union[GroupMessageEvent, PrivateMessageEvent]):
    user = {}
    try:
        resp = await bot.call_api(
            f"contact/v3/users/{event.event.sender.sender_id}",
            method="GET",
            query={"user_id_type": "open_id"},
        )
        info = resp["data"]["user"]
        user["gender"] = _handle_gender(info["gender"])
        user["name"] = info["name"]
        user["avatar"] = info["avatar"]["avatar_origin"]
        user["nickname"] = info["nickname"]
    except ActionFailed:
        pass
    base = {
        "user_id": event.event.sender.sender_id,
        "name": "",
        **user,
    }
    if isinstance(event, GroupMessageEvent):
        chat_id = event.event.message.chat_id
        base["group_id"] = chat_id
        try:
            resp = await bot.call_api(
                f"im/v1/chats/{chat_id}",
                method="GET",
            )
            base["group_name"] = resp["data"]["name"]
            base["group_avatar"] = resp["data"]["avatar"]
            resp1 = await bot.call_api(
                f"contact/v3/users/{resp['data']['owner_id']}",
                method="GET",
                query={"user_id_type": resp["data"]["owner_id_type"]},
            )
            if event.event.sender.sender_id == resp1["data"]["open_id"]:
                base["role"] = Role("OWNER", 100, "owner")
        except ActionFailed:
            pass
    return base
