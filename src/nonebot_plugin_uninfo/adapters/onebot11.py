from nonebot_plugin_uninfo.fetch import InfoFetcher
from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope
from nonebot_plugin_uninfo.model import ChannelType, User, Guild, Channel, Role, MuteInfo, Session

from nonebot.adapters.onebot.v11.event import PrivateMessageEvent, GroupMessageEvent

fetcher = InfoFetcher(SupportAdapter.onebot11)

@fetcher.register(PrivateMessageEvent)
async def _(bot, event: PrivateMessageEvent) -> Session:
    return Session(
        self_id=str(bot.self_id),
        adapter=SupportAdapter.onebot11,
        scope=SupportScope.qq_client,
        user=User(
            id=str(event.user_id),
            name=event.sender.nickname,
        ),
        channel=Channel(
            id=str(event.user_id),
            type=ChannelType.DIRECT,
        )
    )
