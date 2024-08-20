from nonebot_plugin_uninfo import Uninfo
from nonebot import on_command


matcher = on_command("inspect", aliases={"查看"}, priority=1)

@matcher.handle()
async def inspect(session: Uninfo):
    await matcher.send(
        f"Self: {session.self_id}\n"
        f"Adapter: {session.adapter}\n"
        f"User: {session.user.id}\n"
        f"Channel: {session.channel.id}\n"
        f"Guild: {session.guild.id}\n"
        f"Member: {session.member.id}"
    )