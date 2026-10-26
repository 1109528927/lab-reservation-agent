from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from model.access import AccessLog, Passcode, SafetyAck
from model.device import AccessDevice
from model.reservation import Reservation


async def get_ack(
    db: AsyncSession, user_id: int, reservation_id: int
) -> SafetyAck | None:
    stmt = select(SafetyAck).where(
        SafetyAck.user_id == user_id,
        SafetyAck.reservation_id == reservation_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_ack(
    db: AsyncSession, user_id: int, reservation_id: int
) -> SafetyAck:
    row = SafetyAck(user_id=user_id, reservation_id=reservation_id, version="v1")
    db.add(row)
    await db.flush()
    await db.commit()
    await db.refresh(row)
    return row


async def get_active_passcode_for_res(
    db: AsyncSession, reservation_id: int
) -> Passcode | None:
    stmt = select(Passcode).where(
        Passcode.reservation_id == reservation_id,
        Passcode.status == "active",
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_my_passcodes(db: AsyncSession, user_id: int) -> list[Passcode]:
    stmt = (
        select(Passcode)
        .where(Passcode.user_id == user_id)
        .order_by(Passcode.id.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def create_passcode(
    db: AsyncSession,
    *,
    reservation: Reservation,
    user_id: int,
) -> Passcode:
    code = uuid4().hex[:10].upper()
    # 前后各放宽 15 分钟，便于课堂演示联调
    buf = timedelta(minutes=15)
    row = Passcode(
        code=code,
        reservation_id=reservation.id,
        user_id=user_id,
        status="active",
        valid_from=reservation.start_time - buf,
        valid_to=reservation.end_time + buf,
    )
    db.add(row)
    await db.flush()
    await db.commit()
    await db.refresh(row)
    return row


async def get_passcode_by_code(db: AsyncSession, code: str) -> Passcode | None:
    stmt = select(Passcode).where(Passcode.code == code.strip().upper())
    return (await db.execute(stmt)).scalar_one_or_none()


async def add_access_log(
    db: AsyncSession,
    *,
    code: str | None,
    device_id: str | None,
    user_id: int | None,
    reservation_id: int | None,
    allowed: bool,
    reason: str,
) -> AccessLog:
    row = AccessLog(
        code=code,
        device_id=device_id,
        user_id=user_id,
        reservation_id=reservation_id,
        allowed=1 if allowed else 0,
        reason=reason,
    )
    db.add(row)
    await db.flush()
    await db.commit()
    await db.refresh(row)
    return row


async def list_logs(db: AsyncSession, limit: int = 50) -> list[AccessLog]:
    stmt = select(AccessLog).order_by(AccessLog.id.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def passcode_allow_stats(db: AsyncSession, code: str) -> dict:
    """某通行码成功刷入次数与最近一次时间（码仍可在有效期内复用）。"""
    stmt = (
        select(AccessLog)
        .where(AccessLog.code == code.strip().upper(), AccessLog.allowed == 1)
        .order_by(AccessLog.id.desc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    last = rows[0] if rows else None
    return {
        "scan_ok_count": len(rows),
        "last_allowed_at": last.create_at if last else None,
    }


async def get_device_by_device_id(
    db: AsyncSession, device_id: str
) -> AccessDevice | None:
    stmt = select(AccessDevice).where(AccessDevice.device_id == device_id.strip())
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_devices(db: AsyncSession) -> list[AccessDevice]:
    stmt = select(AccessDevice).order_by(AccessDevice.id.asc())
    return list((await db.execute(stmt)).scalars().all())


async def revoke_passcodes_for_reservation(
    db: AsyncSession, reservation_id: int
) -> int:
    """取消预约时作废通行码，避免码仍可刷。"""
    stmt = select(Passcode).where(
        Passcode.reservation_id == reservation_id,
        Passcode.status == "active",
    )
    rows = list((await db.execute(stmt)).scalars().all())
    for row in rows:
        row.status = "revoked"
    if rows:
        await db.flush()
        await db.commit()
    return len(rows)


# -------- 同步版（Agent Tool） --------


def sync_list_labs(session: Session, query: str = "") -> list[dict]:
    from model.lab import Lab

    stmt = select(Lab).where(Lab.status == "open").order_by(Lab.id.desc())
    rows = list(session.execute(stmt).scalars().all())
    q = (query or "").strip().lower()
    out = []
    for r in rows:
        item = {
            "id": r.id,
            "name": r.name,
            "location": r.location,
            "capacity": r.capacity,
            "need_approve": r.need_approve,
        }
        if q and q not in (r.name or "").lower() and q not in (r.location or "").lower():
            continue
        out.append(item)
    return out


def sync_create_reservation(
    session: Session,
    *,
    user_id: int,
    lab_id: int,
    start_time: datetime,
    end_time: datetime,
    purpose: str | None,
) -> dict:
    from model.lab import Lab
    from model.user import User
    from model.schedule import LabScheduleBlock
    from crud.reservation import ACTIVE_STATUSES
    from utils.roles import reservation_status_for_role

    lab = session.get(Lab, lab_id)
    if not lab:
        return {"ok": False, "error": "实验室不存在"}
    if lab.status != "open":
        return {"ok": False, "error": "实验室未开放"}
    if end_time <= start_time:
        return {"ok": False, "error": "结束时间必须晚于开始时间"}

    stmt = select(Reservation).where(
        Reservation.lab_id == lab_id,
        Reservation.status.in_(ACTIVE_STATUSES),
        Reservation.start_time < end_time,
        Reservation.end_time > start_time,
    )
    conflict = session.execute(stmt).scalars().first()
    if conflict:
        return {
            "ok": False,
            "error": f"时段冲突：预约#{conflict.id}",
        }

    block = session.execute(
        select(LabScheduleBlock).where(
            LabScheduleBlock.lab_id == lab_id,
            LabScheduleBlock.start_time < end_time,
            LabScheduleBlock.end_time > start_time,
        )
    ).scalars().first()
    if block:
        return {
            "ok": False,
            "error": f"与排课《{block.title}》冲突（{block.start_time} ~ {block.end_time}）",
        }

    user = session.get(User, user_id)
    role = user.role if user else "student"
    status = reservation_status_for_role(role)
    row = Reservation(
        lab_id=lab_id,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        purpose=purpose,
        status=status,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return {
        "ok": True,
        "id": row.id,
        "status": row.status,
        "message": "已提交，等待管理员审核" if status == "pending" else "已通过（老师可直接预约）",
    }



def sync_my_reservations(session: Session, user_id: int) -> list[dict]:
    stmt = (
        select(Reservation)
        .where(Reservation.user_id == user_id)
        .order_by(Reservation.start_time.desc())
        .limit(20)
    )
    rows = list(session.execute(stmt).scalars().all())
    return [
        {
            "id": r.id,
            "lab_id": r.lab_id,
            "start_time": str(r.start_time),
            "end_time": str(r.end_time),
            "status": r.status,
            "purpose": r.purpose,
        }
        for r in rows
    ]


def sync_get_passcode(session: Session, user_id: int) -> dict:
    now = datetime.now()
    stmt = (
        select(Passcode)
        .where(
            Passcode.user_id == user_id,
            Passcode.status == "active",
            Passcode.valid_to >= now,
        )
        .order_by(Passcode.id.desc())
    )
    row = session.execute(stmt).scalars().first()
    if not row:
        return {"ok": False, "error": "没有有效通行码（需已审批并签署须知后领取）"}
    return {
        "ok": True,
        "code": row.code,
        "reservation_id": row.reservation_id,
        "valid_from": str(row.valid_from),
        "valid_to": str(row.valid_to),
    }
