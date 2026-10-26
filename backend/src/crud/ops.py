"""消息、信用、报修、爽约与过期提醒。"""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.access import AccessLog, Passcode
from model.ops import CreditLog, RepairTicket, UserMessage
from model.reservation import Reservation
from model.user import User

# 信用规则：满分 100；低于阈值不可新预约；每次爽约扣分
CREDIT_MIN_TO_RESERVE = 60
CREDIT_DEDUCT_NO_SHOW = 10
PASS_EXPIRE_HOURS = 2


async def create_message(
    db: AsyncSession,
    *,
    user_id: int,
    msg_type: str,
    title: str,
    content: str,
    related_id: int | None = None,
) -> UserMessage:
    row = UserMessage(
        user_id=user_id,
        msg_type=msg_type,
        title=title,
        content=content,
        related_id=related_id,
        is_read=0,
    )
    db.add(row)
    await db.flush()
    return row


async def message_exists(
    db: AsyncSession,
    *,
    user_id: int,
    msg_type: str,
    related_id: int,
) -> bool:
    stmt = select(UserMessage.id).where(
        UserMessage.user_id == user_id,
        UserMessage.msg_type == msg_type,
        UserMessage.related_id == related_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def list_messages(
    db: AsyncSession,
    user_id: int,
    *,
    only_unread: bool = False,
) -> list[UserMessage]:
    stmt = (
        select(UserMessage)
        .where(UserMessage.user_id == user_id)
        .order_by(UserMessage.id.desc())
    )
    if only_unread:
        stmt = stmt.where(UserMessage.is_read == 0)
    return list((await db.execute(stmt)).scalars().all())


async def unread_count(db: AsyncSession, user_id: int) -> int:
    rows = await list_messages(db, user_id, only_unread=True)
    return len(rows)


async def mark_read(db: AsyncSession, user_id: int, msg_id: int) -> UserMessage | None:
    row = await db.get(UserMessage, msg_id)
    if not row or row.user_id != user_id:
        return None
    row.is_read = 1
    await db.flush()
    return row


async def mark_all_read(db: AsyncSession, user_id: int) -> int:
    rows = await list_messages(db, user_id, only_unread=True)
    for r in rows:
        r.is_read = 1
    await db.flush()
    return len(rows)


async def adjust_credit(
    db: AsyncSession,
    *,
    user: User,
    delta: int,
    reason: str,
    reservation_id: int | None = None,
) -> CreditLog:
    new_score = max(0, min(100, int(user.credit_score or 100) + delta))
    user.credit_score = new_score
    log = CreditLog(
        user_id=user.id,
        delta=delta,
        score_after=new_score,
        reason=reason,
        reservation_id=reservation_id,
    )
    db.add(log)
    await db.flush()
    return log


async def list_credit_logs(db: AsyncSession, user_id: int) -> list[CreditLog]:
    stmt = (
        select(CreditLog)
        .where(CreditLog.user_id == user_id)
        .order_by(CreditLog.id.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_users_credit(db: AsyncSession) -> list[User]:
    stmt = select(User).order_by(User.credit_score.asc(), User.id.asc())
    return list((await db.execute(stmt)).scalars().all())


async def create_repair(
    db: AsyncSession,
    *,
    lab_id: int,
    user_id: int,
    title: str,
    description: str | None,
) -> RepairTicket:
    row = RepairTicket(
        lab_id=lab_id,
        user_id=user_id,
        title=title,
        description=description,
        status="pending",
    )
    db.add(row)
    await db.flush()
    await db.commit()
    await db.refresh(row)
    return row


async def get_repair(db: AsyncSession, ticket_id: int) -> RepairTicket | None:
    return await db.get(RepairTicket, ticket_id)


async def list_repairs_by_user(db: AsyncSession, user_id: int) -> list[RepairTicket]:
    stmt = (
        select(RepairTicket)
        .where(RepairTicket.user_id == user_id)
        .order_by(RepairTicket.id.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_repairs_all(
    db: AsyncSession,
    *,
    status: str | None = None,
) -> list[RepairTicket]:
    stmt = select(RepairTicket).order_by(RepairTicket.id.desc())
    if status:
        stmt = stmt.where(RepairTicket.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def had_successful_access(db: AsyncSession, reservation_id: int) -> bool:
    stmt = select(AccessLog.id).where(
        AccessLog.reservation_id == reservation_id,
        AccessLog.allowed == 1,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def process_no_shows(db: AsyncSession, now: datetime | None = None) -> int:
    """预约已结束且从未成功核验 → 记爽约、扣分、发消息。"""
    now = now or datetime.now()
    stmt = select(Reservation).where(
        Reservation.status.in_(("approved",)),
        Reservation.end_time < now,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    count = 0
    for res in rows:
        if await had_successful_access(db, res.id):
            res.status = "finished"
            continue
        res.status = "no_show"
        user = await db.get(User, res.user_id)
        if user:
            await adjust_credit(
                db,
                user=user,
                delta=-CREDIT_DEDUCT_NO_SHOW,
                reason=f"预约#{res.id}爽约：时段结束未核验",
                reservation_id=res.id,
            )
            await create_message(
                db,
                user_id=user.id,
                msg_type="no_show",
                title="预约已记为爽约",
                content=(
                    f"预约#{res.id}已结束且未成功核验，记为爽约，"
                    f"信用分扣除{CREDIT_DEDUCT_NO_SHOW}分，当前{user.credit_score}分。"
                    f"低于{CREDIT_MIN_TO_RESERVE}分将限制新预约。"
                ),
                related_id=res.id,
            )
        count += 1
    await db.flush()
    await db.commit()
    return count


async def process_pass_expire_reminders(
    db: AsyncSession,
    now: datetime | None = None,
) -> int:
    """通行码将在 PASS_EXPIRE_HOURS 内过期：提醒一次。"""
    now = now or datetime.now()
    until = now + timedelta(hours=PASS_EXPIRE_HOURS)
    stmt = select(Passcode).where(
        Passcode.status == "active",
        Passcode.valid_to > now,
        Passcode.valid_to <= until,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    count = 0
    for pc in rows:
        if await message_exists(
            db, user_id=pc.user_id, msg_type="pass_expire", related_id=pc.id
        ):
            continue
        await create_message(
            db,
            user_id=pc.user_id,
            msg_type="pass_expire",
            title="通行码即将过期",
            content=(
                f"通行码 {pc.code} 将于 {pc.valid_to} 过期，"
                f"请尽快到对应实验室门口核验。"
            ),
            related_id=pc.id,
        )
        count += 1
    if count:
        await db.flush()
        await db.commit()
    return count


async def run_ops_tick(db: AsyncSession) -> dict:
    no_show_n = await process_no_shows(db)
    expire_n = await process_pass_expire_reminders(db)
    return {"no_show": no_show_n, "pass_expire": expire_n}
