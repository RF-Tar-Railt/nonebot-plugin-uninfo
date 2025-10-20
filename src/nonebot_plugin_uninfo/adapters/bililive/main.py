from typing import Optional

from nonebot.adapters.bilibili_live.bot import Bot, WebBot
from nonebot.adapters.bilibili_live.event import (
    AreaRankChangedEvent,
    Event,
    GuardBuyEvent,
    GuardBuyToastEvent,
    LikeEvent,
    MessageEvent,
    PopularRankChangedEvent,
    RoomAdminEntranceEvent,
    RoomAdminRevokeEvent,
    RoomBlockMsgEvent,
    SendGiftEvent,
    _InteractWordEvent,
)
from nonebot.exception import ActionFailed

from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.fetch import BasicInfo
from nonebot_plugin_uninfo.fetch import InfoFetcher as BaseInfoFetcher
from nonebot_plugin_uninfo.model import Member, Scene, SceneType, User


class InfoFetcher(BaseInfoFetcher):
    def extract_user(self, data):
        return User(id=data["user_id"], name=data.get("user_name", data["user_id"]))

    def extract_scene(self, data):
        if "room_id" in data:
            return Scene(
                id=data["room_id"],
                type=SceneType.GROUP,
                name=data.get("room_name", data["room_id"]),
                avatar=data.get("cover", None),
            )
        return Scene(id=data["user_id"], type=SceneType.PRIVATE, name=data.get("user_name", data["user_id"]))

    def extract_member(self, data, user: Optional[User]):
        if user is None:
            user = self.extract_user(data)
        return Member(user, user.name)

    async def query_user(self, bot: Bot, user_id: str):
        return User(user_id, user_id)

    async def query_scene(
        self, bot: Bot, scene_type: SceneType, scene_id: str, *, parent_scene_id: Optional[str] = None
    ):
        base = {"room_id": scene_id}
        try:
            assert isinstance(bot, WebBot)
            room_info = await bot.get_room_info(int(scene_id))
            base |= {
                "room_name": room_info.title,
                "cover": room_info.user_cover,
            }
        except (AssertionError, NotImplementedError, ActionFailed):
            pass
        return self.extract_scene(base)

    async def query_member(self, bot: Bot, scene_type: SceneType, parent_scene_id: str, user_id: str):
        return Member(await self.query_user(bot, user_id), user_id)

    def query_users(self, bot: Bot):
        raise NotImplementedError

    def query_scenes(self, bot: Bot, scene_type: Optional[SceneType] = None, *, parent_scene_id: Optional[str] = None):
        raise NotImplementedError

    def query_members(self, bot: Bot, scene_type: SceneType, parent_scene_id: str):
        raise NotImplementedError

    def supply_self(self, bot: Bot) -> BasicInfo:
        return {
            "self_id": str(bot.self_id),
            "adapter": SupportAdapter.bililive,
            "scope": SupportScope.bililive,
        }


fetcher = InfoFetcher(SupportAdapter.bililive)


@fetcher.supply_wildcard
async def _(bot: Bot, event: Event):
    base = {"room_id": event.room_id}
    try:
        assert isinstance(bot, WebBot)
        room_info = await bot.get_room_info(event.room_id)
        base |= {
            "room_name": room_info.title,
            "cover": room_info.user_cover,
        }
    except (AssertionError, NotImplementedError, ActionFailed):
        pass
    if isinstance(event, MessageEvent):
        base |= {
            "user_id": event.get_user_id(),
            "user_name": event.sender.name,
        }
    elif isinstance(event, (_InteractWordEvent, SendGiftEvent, LikeEvent, RoomBlockMsgEvent)):
        base |= {
            "user_id": event.get_user_id(),
            "user_name": event.uname,
        }
    elif isinstance(event, (GuardBuyEvent, GuardBuyToastEvent)):
        base |= {
            "user_id": event.get_user_id(),
            "user_name": event.username,
        }
    elif isinstance(
        event, (PopularRankChangedEvent, AreaRankChangedEvent, RoomAdminEntranceEvent, RoomAdminRevokeEvent)
    ):
        base |= {
            "user_id": event.get_user_id(),
        }
    else:
        raise NotImplementedError
    return base
