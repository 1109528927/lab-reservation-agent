"""忘记密码申请 CRUD。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.ops import UserMessage
from model.password_reset import PasswordResetRequest
from model.user import User
from utils.security import hash_password


async def create_request(
    db: AsyncSession,
    *,
    username: str,
    employee_no: str | None,
    contact: str | None,
    reason: str | None,
) -> PasswordResetRequest:
    row = PasswordResetRequest(
        username=username,
        employee_no=employee_no,
        contact=contact,
        reason=reason,
        status="pending",
    )
    db.add(row)
    await db.flush()

    admins = list(
        (await db.execute(select(User).where(User.role == "admin"))).scalars().all()
    )
    tip = f"账号 {username}"
    if employee_no:
        tip += f"（学号 {employee_no}）"
    if contact:
        tip += f"，联系 {contact}"
    for a in admins:
        db.add(
            UserMessage(
                user_id=a.id,
                msg_type="password_reset",
                title="忘记密码申请",
                content=(tip + (f"：{reason}" if reason else ""))[:500],
                related_id=row.id,
            )
        )
    await db.commit()
    await db.refresh(row)
    return row


async def list_requests(
    db: AsyncSession, *, status: str | None = None, limit: int = 100
) -> list[PasswordResetRequest]:
    stmt = select(PasswordResetRequest).order_by(PasswordResetRequest.id.desc())
    if status:
        stmt = stmt.where(PasswordResetRequest.status == status)
    stmt = stmt.limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def get_request(db: AsyncSession, req_id: int) -> PasswordResetRequest | None:
    return await db.get(PasswordResetRequest, req_id)


async def resolve_request(
    db: AsyncSession,
    *,
    row: PasswordResetRequest,
    handler_id: int,
    action: str,
    admin_note: str | None,
    new_password: str | None,
) -> dict:
    """
    action=done：可将对应用户密码重置为 new_password（若提供）；
    action=rejected：仅标记驳回。
    """
    if row.status != "pending":
        return {"ok": False, "detail": f"当前状态不可处理：{row.status}"}

    reset_user = None
    if action == "done" and new_password:
        user = await db.execute(select(User).where(User.username == row.username))
        u = user.scalar_one_or_none()
        if not u and row.employee_no:
            u = (
                await db.execute(select(User).where(User.employee_no == row.employee_no))
            ).scalar_one_or_none()
        if not u:
            return {"ok": False, "detail": "未找到对应用户，无法重置密码"}
        u.password = hash_password(new_password)
        reset_user = u.username

    row.status = "done" if action == "done" else "rejected"
    row.handler_id = handler_id
    row.admin_note = (admin_note or "").strip() or None
    await db.commit()
    await db.refresh(row)
    return {
        "ok": True,
        "status": row.status,
        "reset_username": reset_user,
    }
