from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model.reservation import Reservation
from model.schedule import LabScheduleBlock

# 参与冲突判断的状态
ACTIVE_STATUSES = ("pending", "approved", "in_use")


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
    stmt = (
        select(Reservation)
        .where(Reservation.user_id == user_id)
        .order_by(Reservation.start_time.desc())
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

