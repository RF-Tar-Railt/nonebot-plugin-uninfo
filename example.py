from nonebot import on_command, require

require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import QryItrface, Uninfo
from nonebot_plugin_uninfo.constraint import SupportAdapter, SupportScope

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
                f"群组 ID: {session.scene.parent.name + ' | ' if session.scene.parent.name else ''}"
                f"{session.scene.parent.id}"
            )
        else:
            texts.append(
                f"频道 ID: {session.scene.parent.name + ' | ' if session.scene.parent.name else ''}"
                f"{session.scene.parent.id}"
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


matcher1 = on_command("query", aliases={"查询"}, priority=1)


@matcher1.handle()
async def query(interface: QryItrface, session: Uninfo):
    await matcher.send(repr(await interface.get_user(session.user.id)))
    await matcher.send(repr(await interface.get_user(session.user.id)))
