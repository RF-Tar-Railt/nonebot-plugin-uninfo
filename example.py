from nonebot_plugin_uninfo import Uninfo
from nonebot import on_command, on_notice


matcher = on_command("inspect", aliases={"查看"}, priority=1)

@matcher.handle()
async def inspect(session: Uninfo):
    await matcher.send(
        f"Self: {session.self_id}\n"
        f"Adapter: {session.adapter}\n"
        f"Type: {session.scene.type.name}\n"
        f"User: {session.user.id}\n"
        f"Scene: {session.scene.id}\n"
        f"Member: {session.member.id if session.member else 'None'}"
    )


matcher1 = on_notice()

@matcher1.handle()
async def inspect1(session: Uninfo):
    await matcher.send(
        f"Self: {session.self_id}\n"
        f"Adapter: {session.adapter}\n"
        f"Type: {session.scene.type.name}\n"
        f"User: {session.user.id}\n"
        f"Scene: {session.scene.id}\n"
        f"Member: {session.member.id if session.member else 'None'}"
    )    