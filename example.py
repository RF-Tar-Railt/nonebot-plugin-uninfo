from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope

from nonebot import on_command, on_notice


matcher = on_command("inspect", aliases={"查看"}, priority=1)


@matcher.handle()
async def inspect(session: Uninfo):
    adapter = session.adapter.name if isinstance(session.adapter, SupportAdapter) else str(session.adapter)
    scope = session.scope.name if isinstance(session.scope, SupportScope) else str(session.scope)
    texts = [
        f"平台名: {adapter} | {scope}",
        f"用户ID: {session.user.name + ' | ' if session.user.name else ''}{session.user.id}",
        f"自身ID: {session.self_id}",
        f"事件场景: {session.scene.type.name}",
    ]
    if session.scene.parent:
        if session.scene.is_private:
            texts.append(
                f"群组 ID: {session.scene.parent.name + ' | ' if session.scene.parent.name else ''}{session.scene.parent.id}"
            )
        else:
            texts.append(
                f"频道 ID: {session.scene.parent.name + ' | ' if session.scene.parent.name else ''}{session.scene.parent.id}"
            )
    if session.scene.is_group:
        texts.append(f"群组 ID: {session.scene.name + ' | ' if session.scene.name else ''}{session.scene.id}")
    elif session.scene.is_guild:
        texts.append(f"频道 ID: {session.scene.name + ' | ' if session.scene.name else ''}{session.scene.id}")
    elif session.scene.is_private:
        texts.append(f"私信 ID: {session.scene.name + ' | ' if session.scene.name else ''}{session.scene.id}")
    else:
        texts.append(f"子频道 ID: {session.scene.name + ' | ' if session.scene.name else ''}{session.scene.id}")
    if session.member:
        texts.append(f"成员 ID: {session.member.nick + ' | ' if session.member.nick else ''}{session.member.id}")
    await matcher.send("\n".join(texts))


matcher1 = on_notice()

@matcher1.handle()
async def inspect1(session: Uninfo):
    await matcher.send(
        f"Self: {session.self_id}\n"
        f"Adapter: {session.adapter}\n"
        f"Scope: {session.scope}\n"
        f"Type: {session.scene.type.name}\n"
        f"User: {session.user.id}\n"
        f"Scene: {session.scene.id}\n"
        f"Member: {session.member.id if session.member else 'None'}"
    )
