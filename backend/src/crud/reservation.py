from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from model.reservation import Reservation
from model.schedule import LabScheduleBlock

# 参与冲突判断的状态
ACTIVE_STATUSES = ("pending", "approved", "in_use")

EXPIRED_PENDING_REASON = "时段已过期，系统自动作废"
# 单次预约最长时长；需要更久可紧接着再约下一段（不冲突即可续约）
MAX_RESERVATION_HOURS = 2


def assert_not_past_range(start_time: datetime, end_time: datetime, *, now: datetime | None = None) -> str | None:
    """返回错误文案；通过则返回 None。含「未过期 + 单次≤2小时」。"""
    now = now or datetime.now()
    if end_time <= start_time:
        return "结束时间必须晚于开始时间"
    if start_time < now:
        return "不能预约已过去的时段，请选择当前时间之后的开始时间"
    hours = (end_time - start_time).total_seconds() / 3600.0
    if hours > MAX_RESERVATION_HOURS + 1e-6:
        return (
            f"单次预约最长 {MAX_RESERVATION_HOURS} 小时；"
            "若需更久，可在本段结束后另约下一段（时段不冲突即可续约）"
        )
    return None


async def expire_stale_pending(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    """待审单开始时间已过 → 标为 expired，并从待审批列表消失。"""
    now = now or datetime.now()
    result = await db.execute(
        update(Reservation)
        .where(
            Reservation.status == "pending",
            Reservation.start_time < now,
        )
        .values(status="expired", reject_reason=EXPIRED_PENDING_REASON)
    )
    await db.commit()
    return int(result.rowcount or 0)


def sync_expire_stale_pending(session: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.now()
    result = session.execute(
        update(Reservation)
        .where(
            Reservation.status == "pending",
            Reservation.start_time < now,
        )
        .values(status="expired", reject_reason=EXPIRED_PENDING_REASON)
    )
    session.commit()
    return int(result.rowcount or 0)


async def find_conflict(
    db: AsyncSession,
    *,
    lab_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_id: int | None = None,
) -> Reservation | None:
    """区间重叠：existing.start < new.end AND existing.end > new.start"""
    stmt = select(Reservation).where(
        Reservation.lab_id == lab_id,
        Reservation.status.in_(ACTIVE_STATUSES),
        Reservation.start_time < end_time,
        Reservation.end_time > start_time,
    )
    if exclude_id is not None:
        stmt = stmt.where(Reservation.id != exclude_id)
    return (await db.execute(stmt)).scalars().first()


async def find_schedule_conflict(
    db: AsyncSession,
    *,
    lab_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_id: int | None = None,
) -> LabScheduleBlock | None:
    """与教务排课占档重叠。"""
    stmt = select(LabScheduleBlock).where(
        LabScheduleBlock.lab_id == lab_id,
        LabScheduleBlock.start_time < end_time,
        LabScheduleBlock.end_time > start_time,
    )
    if exclude_id is not None:
        stmt = stmt.where(LabScheduleBlock.id != exclude_id)
    return (await db.execute(stmt)).scalars().first()



async def create_reservation(
    db: AsyncSession,
    *,
    lab_id: int,
    user_id: int,
    start_time: datetime,
    end_time: datetime,
    purpose: str | None,
    status: str,
) -> Reservation:
    row = Reservation(
        lab_id=lab_id,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        purpose=purpose,
        status=status,
    )
    db.add(row)
    await db.flush()
    await db.commit()
    await db.refresh(row)
    return row


async def get_reservation(db: AsyncSession, res_id: int) -> Reservation | None:
    return await db.get(Reservation, res_id)


async def list_by_user(db: AsyncSession, user_id: int) -> list[Reservation]:
    # 按操作/提交时间倒序（最新操作在前），不以预约时段排序
    stmt = (
        select(Reservation)
        .where(Reservation.user_id == user_id)
        .order_by(Reservation.create_at.desc(), Reservation.id.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_all(
    db: AsyncSession,
    *,
    status: str | None = None,
) -> list[Reservation]:
    stmt = select(Reservation).order_by(Reservation.id.desc())
    if status:
        stmt = stmt.where(Reservation.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def list_active_on_day(
    db: AsyncSession,
    *,
    lab_id: int,
    day_start: datetime,
    day_end: datetime,
) -> list[Reservation]:
    stmt = (
        select(Reservation)
        .where(
            Reservation.lab_id == lab_id,
            Reservation.status.in_(ACTIVE_STATUSES),
            Reservation.start_time < day_end,
            Reservation.end_time > day_start,
        )
        .order_by(Reservation.start_time.asc())
    )
    return list((await db.execute(stmt)).scalars().all())

