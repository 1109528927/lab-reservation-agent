from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from model.agent_chat import AgentChatMessage

DEFAULT_KEEP = 100


async def list_recent_for_user(
    db: AsyncSession,
    *,
    user_id: int,
    limit: int = DEFAULT_KEEP,
) -> list[AgentChatMessage]:
    """按用户取最近 N 条（跨登录可见），时间正序便于 UI 从上往下读。"""
    cap = max(1, min(int(limit or DEFAULT_KEEP), 200))
    recent = list(
        (
            await db.execute(
                select(AgentChatMessage)
                .where(AgentChatMessage.user_id == user_id)
                .order_by(AgentChatMessage.id.desc())
                .limit(cap)
            )
        )
        .scalars()
        .all()
    )
    recent.reverse()
    return recent


def _prune_sync(session: Session, user_id: int, keep: int = DEFAULT_KEEP) -> None:
    ids = list(
        session.execute(
            select(AgentChatMessage.id)
            .where(AgentChatMessage.user_id == user_id)
            .order_by(AgentChatMessage.id.desc())
        )
        .scalars()
        .all()
    )
    if len(ids) <= keep:
        return
    drop = ids[keep:]
    session.execute(
        delete(AgentChatMessage).where(AgentChatMessage.id.in_(drop))
    )


def sync_append_pair(
    session: Session,
    *,
    user_id: int,
    thread_id: str,
    user_text: str,
    assistant_text: str,
    keep: int = DEFAULT_KEEP,
) -> None:
    """流式结束后同步写入一轮对话，并裁剪该用户超出 keep 的旧记录。"""
    u = (user_text or "").strip()
    a = (assistant_text or "").strip()
    if u:
        session.add(
            AgentChatMessage(
                user_id=user_id, thread_id=thread_id, role="user", content=u
            )
        )
    if a:
        session.add(
            AgentChatMessage(
                user_id=user_id, thread_id=thread_id, role="assistant", content=a
            )
        )
    session.flush()
    _prune_sync(session, user_id, keep=keep)
    session.commit()
