from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from model.access import AccessLog, Passcode, SafetyAck
from model.device import AccessDevice
from model.reservation import Reservation

# 与 Agent Tool / 签署须知共用（router.access 引用）
SAFETY_TEXT_V1 = (
    "进入实验室须遵守安全规定：禁止违规用电、食品饮料远离设备、"
    "离开前断电关窗。本人已阅读并同意上述须知。"
)


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


def _norm_text(s: str) -> str:
    """去空白便于「嵌入式实验室A」匹配「嵌入式实验室 A」。"""
    return "".join((s or "").lower().split())


def sync_pick_free_slot(
    session: Session,
    *,
    prefer_lab_name: str = "",
    day_offset: int = 1,
    prefer: str = "pm",
    exclude_lab_name: str = "",
    exclude_lab_id: int = 0,
) -> dict:
    """自动挑一间开放实验室 + 空闲时段（给助手少轮问询用）。"""
    from model.schedule import LabScheduleBlock
    from crud.reservation import ACTIVE_STATUSES

    now = datetime.now()
    day = (now + timedelta(days=max(0, int(day_offset)))).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day_end = day + timedelta(days=1)

    # 单次最长 2 小时
    presets = {
        "am": [(8, 0, 10, 0), (9, 0, 11, 0), (10, 0, 12, 0), (11, 0, 13, 0)],
        "pm": [(12, 0, 14, 0), (14, 0, 16, 0), (15, 0, 17, 0), (16, 0, 18, 0)],
        "eve": [(18, 30, 20, 30), (19, 0, 21, 0)],
        "any": [
            (8, 0, 10, 0),
            (9, 0, 11, 0),
            (10, 0, 12, 0),
            (11, 0, 13, 0),
            (12, 0, 14, 0),
            (14, 0, 16, 0),
            (15, 0, 17, 0),
            (16, 0, 18, 0),
            (18, 30, 20, 30),
            (19, 0, 21, 0),
        ],
    }
    key = (prefer or "pm").strip().lower()
    slots = presets.get(key) or presets["pm"]
    # any：把 prefer 档放前面再补全
    if key in ("am", "pm", "eve"):
        rest = [x for x in presets["any"] if x not in slots]
        slots = list(slots) + rest

    labs = sync_list_labs(session, query=prefer_lab_name or "")
    if not labs:
        labs = sync_list_labs(session, query="")
    # 稳定顺序，避免每次「换选」像随机跳实验室
    labs = sorted(labs, key=lambda x: int(x["id"]))
    excl_name = _norm_text(exclude_lab_name or "")
    excl_id = int(exclude_lab_id or 0)
    if excl_name or excl_id:
        filtered = []
        for x in labs:
            if excl_id and int(x["id"]) == excl_id:
                continue
            if excl_name and excl_name in _norm_text(str(x.get("name") or "")):
                continue
            filtered.append(x)
        # 若过滤后为空，回退全量（避免无档可约）
        if filtered:
            labs = filtered
    if not labs:
        return {"ok": False, "error": "暂无开放实验室", "today": str(now.date())}

    # 若选今天，丢掉已开始的档
    def still_open(h0, m0) -> bool:
        st = day.replace(hour=h0, minute=m0)
        return st >= now

    for lab in labs:
        lab_id = int(lab["id"])
        busy = []
        for r in session.execute(
            select(Reservation).where(
                Reservation.lab_id == lab_id,
                Reservation.status.in_(ACTIVE_STATUSES),
                Reservation.start_time < day_end,
                Reservation.end_time > day,
            )
        ).scalars():
            busy.append((r.start_time, r.end_time))
        for b in session.execute(
            select(LabScheduleBlock).where(
                LabScheduleBlock.lab_id == lab_id,
                LabScheduleBlock.start_time < day_end,
                LabScheduleBlock.end_time > day,
            )
        ).scalars():
            busy.append((b.start_time, b.end_time))

        for h0, m0, h1, m1 in slots:
            st = day.replace(hour=h0, minute=m0)
            et = day.replace(hour=h1, minute=m1)
            if day.date() == now.date() and not still_open(h0, m0):
                continue
            hit = any(a < et and b > st for a, b in busy)
            if hit:
                continue
            return {
                "ok": True,
                "lab_id": lab_id,
                "lab_name": lab["name"],
                "location": lab.get("location"),
                "start_time": st.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": et.strftime("%Y-%m-%d %H:%M:%S"),
                "day_offset": int(day_offset),
                "today": str(now.date()),
                "hint": "可直接用 create_reservation(confirm=false) 预检，复述后等用户确认",
            }

    return {
        "ok": False,
        "error": "所选日期常见时段均被占，请换一天或换实验室名再试",
        "today": str(now.date()),
        "day_offset": int(day_offset),
    }


def sync_list_labs(
    session: Session, query: str = "", min_capacity: int | None = None
) -> list[dict]:
    from model.lab import Lab

    stmt = select(Lab).where(Lab.status == "open").order_by(Lab.id.desc())
    rows = list(session.execute(stmt).scalars().all())
    q = _norm_text(query or "")
    min_cap = int(min_capacity) if min_capacity is not None else None
    devices = list(
        session.execute(
            select(AccessDevice).where(AccessDevice.status == "active")
        ).scalars().all()
    )
    devices_by_lab: dict[int, list[str]] = {}
    for d in devices:
        devices_by_lab.setdefault(int(d.lab_id), []).append(d.device_id)
    out = []
    for r in rows:
        name_n = _norm_text(r.name or "")
        loc_n = _norm_text(r.location or "")
        if q and q not in name_n and q not in loc_n:
            continue
        cap = int(r.capacity or 0)
        if min_cap is not None and cap < min_cap:
            continue
        door_ids = devices_by_lab.get(int(r.id), [])
        # 对用户话术勿吐 need_approve / 设备号；内部办理仍用 id
        out.append(
            {
                "id": r.id,
                "name": r.name,
                "location": r.location,
                "capacity": r.capacity,
                "has_door": bool(door_ids),
            }
        )
    return out


def sync_preview_reservation(
    session: Session,
    *,
    user_id: int,
    lab_id: int,
    start_time: datetime,
    end_time: datetime,
    purpose: str | None,
) -> dict:
    """确认门预检：与建约同一套冲突/排课规则，不写库。"""
    from model.lab import Lab
    from model.user import User
    from model.schedule import LabScheduleBlock
    from crud.reservation import ACTIVE_STATUSES
    from utils.roles import reservation_status_for_role

    from crud.reservation import assert_not_past_range

    lab = session.get(Lab, lab_id)
    if not lab:
        return {"ok": False, "error": "实验室不存在", "suggest": "换一间开放实验室"}
    if lab.status != "open":
        return {"ok": False, "error": "实验室未开放", "suggest": "换开放中的实验室"}
    past_err = assert_not_past_range(start_time, end_time)
    if past_err:
        return {"ok": False, "error": past_err, "suggest": "改选今天稍后或未来日期的时段"}

    stmt = select(Reservation).where(
        Reservation.lab_id == lab_id,
        Reservation.status.in_(ACTIVE_STATUSES),
        Reservation.start_time < end_time,
        Reservation.end_time > start_time,
    )
    conflict = session.execute(stmt).scalars().first()
    if conflict:
        mine = int(conflict.user_id) == int(user_id)
        return {
            "ok": False,
            "written": False,
            "error": (
                f"该时段你已有预约（{conflict.start_time} ~ {conflict.end_time}）"
                if mine
                else f"时段已被占用（{conflict.start_time} ~ {conflict.end_time}）"
            ),
            "suggest": "请换时段/换实验室，或先取消冲突预约后再约",
            "conflict_reservation_id": conflict.id,
            "must_tell_user": True,
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
            "suggest": "换时段或换实验室",
        }

    user = session.get(User, user_id)
    role = user.role if user else "student"
    status = reservation_status_for_role(role, lab.need_approve)
    return {
        "ok": True,
        "needs_confirm": True,
        "lab_id": lab.id,
        "lab_name": lab.name,
        "location": lab.location,
        "need_approve": int(lab.need_approve or 0),
        "start_time": str(start_time),
        "end_time": str(end_time),
        "purpose": purpose,
        "will_status": status,
        "summary": (
            f"预检通过：{lab.name}（{lab.location}），"
            f"{start_time} ~ {end_time}，落库后状态将为 {status}。"
            "请向用户复述实验室名、时段与状态，不要提审批开关或门口设备号；"
            "等待明确「确认」后再写库。"
        ),
    }


def sync_create_reservation(
    session: Session,
    *,
    user_id: int,
    lab_id: int,
    start_time: datetime,
    end_time: datetime,
    purpose: str | None,
) -> dict:
    preview = sync_preview_reservation(
        session,
        user_id=user_id,
        lab_id=lab_id,
        start_time=start_time,
        end_time=end_time,
        purpose=purpose,
    )
    if not preview.get("ok"):
        return preview

    status = preview["will_status"]
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
        "written": True,
        "id": row.id,
        "status": row.status,
        "lab_id": lab_id,
        "lab_name": preview.get("lab_name"),
        "message": (
            "已提交，等待管理员审核"
            if status == "pending"
            else (
                "已通过（免审实验室）"
                if preview.get("need_approve") == 0
                else "已通过（老师/管理员可直接预约）"
            )
        ),
    }


def sync_get_my_reservation(
    session: Session, *, user_id: int, reservation_id: int
) -> dict | None:
    """按 id 取本人预约（不限 list 的 20 条窗口）。"""
    from model.lab import Lab

    row = session.get(Reservation, reservation_id)
    if not row or int(row.user_id) != int(user_id):
        return None
    lab = session.get(Lab, row.lab_id)
    return {
        "id": row.id,
        "lab_id": row.lab_id,
        "lab_name": lab.name if lab else None,
        "start_time": str(row.start_time),
        "end_time": str(row.end_time),
        "status": row.status,
        "purpose": row.purpose,
        "create_at": str(row.create_at) if row.create_at else None,
    }


def sync_cancel_reservation(
    session: Session, *, user_id: int, reservation_id: int
) -> dict:
    row = session.get(Reservation, reservation_id)
    if not row:
        return {"ok": False, "error": "预约不存在", "id": reservation_id}
    if row.user_id != user_id:
        return {"ok": False, "error": "只能取消自己的预约", "id": reservation_id}
    if row.status == "cancelled":
        return {
            "ok": True,
            "written": False,
            "id": reservation_id,
            "status": "cancelled",
            "message": "该预约此前已取消",
        }
    if row.status not in ("pending", "approved", "in_use"):
        return {
            "ok": False,
            "error": f"当前状态不可取消：{row.status}",
            "id": reservation_id,
        }
    row.status = "cancelled"
    session.flush()
    pcs = list(
        session.execute(
            select(Passcode).where(
                Passcode.reservation_id == reservation_id,
                Passcode.status == "active",
            )
        ).scalars().all()
    )
    for pc in pcs:
        pc.status = "revoked"
    session.flush()
    from model.lab import Lab

    lab = session.get(Lab, int(row.lab_id)) if row.lab_id else None
    return {
        "ok": True,
        "written": True,
        "id": reservation_id,
        "status": "cancelled",
        "lab_id": int(row.lab_id) if row.lab_id else None,
        "lab_name": lab.name if lab else None,
        "start_time": str(row.start_time),
        "end_time": str(row.end_time),
        "revoked_passcodes": len(pcs),
    }


def sync_ack_safety(
    session: Session, *, user_id: int, reservation_id: int
) -> dict:
    row = session.get(Reservation, reservation_id)
    if not row:
        return {"ok": False, "error": "预约不存在"}
    if row.user_id != user_id:
        return {"ok": False, "error": "只能签署自己的预约须知"}
    if row.status not in ("approved", "in_use"):
        return {"ok": False, "error": "仅已通过的预约可签署须知"}
    existed = session.execute(
        select(SafetyAck).where(
            SafetyAck.user_id == user_id,
            SafetyAck.reservation_id == reservation_id,
        )
    ).scalar_one_or_none()
    if existed:
        return {"ok": True, "acked": True, "message": "已签署过", "written": False}
    session.add(
        SafetyAck(user_id=user_id, reservation_id=reservation_id, version="v1")
    )
    session.flush()
    return {
        "ok": True,
        "acked": True,
        "written": True,
        "safety_text": SAFETY_TEXT_V1,
        "message": "签署成功",
    }


def sync_issue_passcode(
    session: Session, *, user_id: int, reservation_id: int
) -> dict:
    row = session.get(Reservation, reservation_id)
    if not row:
        return {"ok": False, "error": "预约不存在"}
    if row.user_id != user_id:
        return {"ok": False, "error": "只能领取自己的通行码"}
    if row.status not in ("approved", "in_use"):
        return {"ok": False, "error": "预约未通过，无法发码"}
    ack = session.execute(
        select(SafetyAck).where(
            SafetyAck.user_id == user_id,
            SafetyAck.reservation_id == reservation_id,
        )
    ).scalar_one_or_none()
    if not ack:
        return {"ok": False, "error": "请先签署安全须知"}
    existed = session.execute(
        select(Passcode).where(
            Passcode.reservation_id == reservation_id,
            Passcode.status == "active",
        )
    ).scalars().first()
    if existed:
        return {
            "ok": True,
            "written": False,
            "code": existed.code,
            "reservation_id": reservation_id,
            "valid_from": str(existed.valid_from),
            "valid_to": str(existed.valid_to),
            "message": "已有有效通行码",
        }
    buf = timedelta(minutes=15)
    code = uuid4().hex[:10].upper()
    pc = Passcode(
        code=code,
        reservation_id=reservation_id,
        user_id=user_id,
        status="active",
        valid_from=row.start_time - buf,
        valid_to=row.end_time + buf,
    )
    session.add(pc)
    session.flush()
    return {
        "ok": True,
        "written": True,
        "code": code,
        "reservation_id": reservation_id,
        "valid_from": str(pc.valid_from),
        "valid_to": str(pc.valid_to),
        "message": "发码成功",
        "ui": "passcode_qr",
    }


def sync_access_help(session: Session, *, user_id: int, lab_hint: str = "") -> dict:
    """根据最近核验流水 + 本人有效预约 + 门禁绑定解释「进不去」。"""
    from model.lab import Lab

    stmt = (
        select(AccessLog)
        .where(AccessLog.user_id == user_id)
        .order_by(AccessLog.id.desc())
        .limit(8)
    )
    logs = list(session.execute(stmt).scalars().all())
    items = []
    for lg in logs:
        items.append(
            {
                "allowed": bool(lg.allowed),
                "reason": lg.reason,
                "at": str(lg.create_at) if lg.create_at else None,
            }
        )
    latest = items[0] if items else None

    active_res = list(
        session.execute(
            select(Reservation)
            .where(
                Reservation.user_id == user_id,
                Reservation.status.in_(("pending", "approved", "in_use")),
            )
            .order_by(Reservation.start_time.desc())
            .limit(5)
        ).scalars().all()
    )
    lab_ids = {int(r.lab_id) for r in active_res}
    labs_map: dict[int, Lab] = {}
    if lab_ids:
        for lab in session.execute(select(Lab).where(Lab.id.in_(lab_ids))).scalars():
            labs_map[int(lab.id)] = lab
    devices = list(
        session.execute(
            select(AccessDevice).where(AccessDevice.status == "active")
        ).scalars().all()
    )
    door_by_lab: dict[int, list[dict]] = {}
    for d in devices:
        door_by_lab.setdefault(int(d.lab_id), []).append(
            {"device_id": d.device_id, "name": d.name}
        )

    bookings = []
    for r in active_res:
        lab = labs_map.get(int(r.lab_id))
        doors = door_by_lab.get(int(r.lab_id), [])
        bookings.append(
            {
                "reservation_id": r.id,
                "lab_id": r.lab_id,
                "lab_name": lab.name if lab else None,
                "status": r.status,
                "start_time": str(r.start_time),
                "end_time": str(r.end_time),
                "has_door": bool(doors),
                "door_hint": (
                    f"请到「{lab.name if lab else '对应实验室'}」绑定门口刷码"
                    if doors
                    else "该实验室尚未绑定门禁，无法核验"
                ),
            }
        )

    hint_labs = (
        sync_list_labs(session, query=lab_hint.strip()) if lab_hint.strip() else []
    )

    advice = "暂无本人核验流水：请确认是否已领码、是否到预约时段、是否刷对实验室门口。"
    if latest:
        if latest["allowed"]:
            advice = "最近一次核验已通过。若仍进不去，检查是否刷错门或门禁硬件离线。"
        else:
            advice = f"最近拒绝原因：{latest['reason']}。"
            if latest["reason"] and "非本实验室" in latest["reason"]:
                advice += " 您刷的门口与预约实验室不一致。"
            elif latest["reason"] == "不在有效时段内":
                advice += " 请等到预约有效时段再刷（含开场前约 15 分钟缓冲）。"
            elif latest["reason"] == "未知门禁设备":
                advice += " 请到预约实验室对应的门口设备刷码。"
    if bookings:
        tips = []
        for b in bookings:
            tips.append(
                f"预约#{b['reservation_id']}「{b['lab_name']}」：{b['door_hint']}"
            )
        advice += " 对照：" + "；".join(tips) + "。"
    if lab_hint.strip():
        if hint_labs:
            bits = [
                f"{lab['name']}（{'有门禁' if lab.get('has_door') else '未绑门禁'}）"
                for lab in hint_labs
            ]
            advice += f" 关键词「{lab_hint}」：" + "；".join(bits) + "。"
        else:
            advice += f" 关键词「{lab_hint}」未匹配到开放实验室。"

    return {
        "ok": True,
        "latest": latest,
        "recent": items,
        "bookings": bookings,
        "hint_labs": hint_labs,
        "advice": advice,
    }



_ACTIVE_RES_STATUSES = ("pending", "approved", "in_use")


def sync_my_reservations(session: Session, user_id: int) -> list[dict]:
    from model.lab import Lab

    stmt = (
        select(Reservation)
        .where(Reservation.user_id == user_id)
        .order_by(Reservation.create_at.desc(), Reservation.id.desc())
        .limit(20)
    )
    rows = list(session.execute(stmt).scalars().all())
    lab_ids = {int(r.lab_id) for r in rows}
    labs: dict[int, Lab] = {}
    if lab_ids:
        for lab in session.execute(select(Lab).where(Lab.id.in_(lab_ids))).scalars():
            labs[int(lab.id)] = lab
    devices = list(
        session.execute(
            select(AccessDevice).where(AccessDevice.status == "active")
        ).scalars().all()
    )
    doors_by_lab: dict[int, list[str]] = {}
    for d in devices:
        doors_by_lab.setdefault(int(d.lab_id), []).append(d.device_id)
    return [
        {
            "id": r.id,
            "lab_id": r.lab_id,
            "lab_name": labs[r.lab_id].name if r.lab_id in labs else None,
            "door_device_ids": doors_by_lab.get(int(r.lab_id), []),
            "start_time": str(r.start_time),
            "end_time": str(r.end_time),
            "status": r.status,
            "purpose": r.purpose,
            "create_at": str(r.create_at) if r.create_at else None,
        }
        for r in rows
    ]


def sync_my_active_reservations(session: Session, user_id: int) -> list[dict]:
    """仅 pending/approved/in_use，按 id 倒序（不限最近 20 条窗口里的历史单）。"""
    from model.lab import Lab

    stmt = (
        select(Reservation)
        .where(
            Reservation.user_id == user_id,
            Reservation.status.in_(_ACTIVE_RES_STATUSES),
        )
        .order_by(Reservation.id.desc())
    )
    rows = list(session.execute(stmt).scalars().all())
    lab_ids = {int(r.lab_id) for r in rows}
    labs: dict[int, Lab] = {}
    if lab_ids:
        for lab in session.execute(select(Lab).where(Lab.id.in_(lab_ids))).scalars():
            labs[int(lab.id)] = lab
    return [
        {
            "id": int(r.id),
            "lab_id": r.lab_id,
            "lab_name": labs[r.lab_id].name if r.lab_id in labs else None,
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
