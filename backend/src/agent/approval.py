"""管理员侧：规则自动审批（纯代码闸门，不调用大模型）。

原则：
- 硬条件 + 资格路径全部满足：可自动通过（省管理员点按钮）
- 规则不过：列入 need_human，不自动驳回、不自动改库（人在环）
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from pathlib import Path
from sqlalchemy import select

from config.request import SyncSessionLocal
from model.lab import Lab
from model.ops import UserMessage
from model.reservation import Reservation
from model.user import User

# 自动通过门槛（可环境变量覆盖）
# 与业务单次最长 2 小时对齐（可环境变量覆盖）
MAX_HOURS = float(os.getenv("LAB_AUTO_APPROVE_MAX_HOURS", "2"))
REQUIRE_PURPOSE = os.getenv("LAB_AUTO_APPROVE_REQUIRE_PURPOSE", "1") != "0"
# 历史成功预约达到该次数，可放宽「用途必填」等软条件
MIN_HISTORY = int(os.getenv("LAB_AUTO_APPROVE_MIN_HISTORY", "2"))
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
TRUSTED_NOS_FILE = Path(
    os.getenv(
        "LAB_TRUSTED_EMPLOYEE_NOS_FILE",
        str(_BACKEND_ROOT / "data" / "trusted_employee_nos.txt"),
    )
)
# 计入「有预约记录」的历史状态
_HISTORY_STATUSES = ("approved", "in_use", "completed", "closed")


def load_trusted_employee_nos() -> set[str]:
    """管理员录入的可信工号：文件一行一个，可加环境变量逗号列表。"""
    nos: set[str] = set()
    env = (os.getenv("LAB_TRUSTED_EMPLOYEE_NOS") or "").strip().strip("\r")
    if env:
        for part in env.replace(";", ",").split(","):
            p = part.strip()
            if p:
                nos.add(p)
    if TRUSTED_NOS_FILE.is_file():
        for line in TRUSTED_NOS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            nos.add(line.split()[0])
    return nos


def add_trusted_employee_no(employee_no: str) -> dict[str, Any]:
    no = (employee_no or "").strip()
    if not no:
        return {"ok": False, "error": "工号为空"}
    TRUSTED_NOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = load_trusted_employee_nos()
    if no in existing:
        return {"ok": True, "employee_no": no, "message": "已在白名单中", "added": False}
    with TRUSTED_NOS_FILE.open("a", encoding="utf-8") as f:
        f.write(no + "\n")
    return {"ok": True, "employee_no": no, "message": "已录入可信工号", "added": True}


def count_prior_approved(db, user_id: int) -> int:
    rows = (
        db.execute(
            select(Reservation.id).where(
                Reservation.user_id == int(user_id),
                Reservation.status.in_(_HISTORY_STATUSES),
            )
        )
        .scalars()
        .all()
    )
    return len(list(rows))


def _dump_pending(
    row: Reservation,
    lab: Lab | None,
    user: User | None,
    *,
    prior_approved_count: int = 0,
    trusted_employee: bool = False,
) -> dict[str, Any]:
    hours = (row.end_time - row.start_time).total_seconds() / 3600.0
    return {
        "id": row.id,
        "lab_id": row.lab_id,
        "lab_name": lab.name if lab else "",
        "user_id": row.user_id,
        "username": user.username if user else "",
        "employee_no": (user.employee_no if user else "") or "",
        "role": user.role if user else "",
        "credit_score": int(user.credit_score or 100) if user else None,
        "start_time": row.start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": row.end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "hours": round(hours, 2),
        "purpose": row.purpose or "",
        "status": row.status,
        "prior_approved_count": int(prior_approved_count),
        "trusted_employee": bool(trusted_employee),
    }


def list_pending(*, limit: int = 20) -> list[dict[str, Any]]:
    from crud.reservation import sync_expire_stale_pending

    trusted = load_trusted_employee_nos()
    with SyncSessionLocal() as db:
        sync_expire_stale_pending(db)
        rows = list(
            db.execute(
                select(Reservation)
                .where(Reservation.status == "pending")
                .order_by(Reservation.id.asc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            lab = db.get(Lab, row.lab_id)
            user = db.get(User, row.user_id)
            prior = count_prior_approved(db, row.user_id)
            emp = (user.employee_no if user else "") or ""
            out.append(
                _dump_pending(
                    row,
                    lab,
                    user,
                    prior_approved_count=prior,
                    trusted_employee=emp in trusted,
                )
            )
        return out


def rule_gate(item: dict[str, Any]) -> dict[str, Any]:
    """确定性规则。硬条件不过则禁止自动通过；软条件可用历史/可信工号放宽。"""
    hard_fails: list[str] = []
    soft_fails: list[str] = []
    paths: list[str] = []

    hours = float(item.get("hours") or 0)
    if hours <= 0:
        hard_fails.append("时段非法")
    if hours > MAX_HOURS:
        hard_fails.append(f"时长超过 {MAX_HOURS} 小时")
    credit = item.get("credit_score")
    if credit is not None and int(credit) < 60:
        hard_fails.append("信用分过低")
    try:
        st = datetime.strptime(item["start_time"], "%Y-%m-%d %H:%M:%S")
        if st.hour >= 22 or st.hour < 6:
            hard_fails.append("深夜时段需人工审")
    except Exception:
        hard_fails.append("时间解析失败")

    purpose = (item.get("purpose") or "").strip()
    purpose_ok = (not REQUIRE_PURPOSE) or len(purpose) >= 4
    if not purpose_ok:
        soft_fails.append("用途过短或为空")

    prior = int(item.get("prior_approved_count") or 0)
    history_ok = prior >= MIN_HISTORY
    trusted = bool(item.get("trusted_employee"))
    emp = (item.get("employee_no") or "").strip()

    # 三条资格路径：任一条 + 硬条件通过 → 规则闸门 ok
    if purpose_ok:
        paths.append("purpose_ok")
    if history_ok:
        paths.append(f"history>={MIN_HISTORY}(实际{prior})")
    if trusted and emp:
        paths.append(f"trusted_employee_no={emp}")

    ok = (not hard_fails) and bool(paths)
    if not paths and not hard_fails:
        soft_fails.append(
            f"未命中资格路径（用途合格 / 历史成功预约≥{MIN_HISTORY} / 工号在白名单）"
        )

    return {
        "ok": ok,
        "fails": hard_fails + ([] if ok else soft_fails),
        "hard_fails": hard_fails,
        "soft_fails": soft_fails,
        "eligibility_paths": paths,
        "prior_approved_count": prior,
        "trusted_employee": trusted,
        "employee_no": emp,
        "min_history": MIN_HISTORY,
    }


def review_one(reservation_id: int) -> dict[str, Any]:
    """只跑规则闸门，不调用大模型。"""
    with SyncSessionLocal() as db:
        row = db.get(Reservation, int(reservation_id))
        if not row:
            return {"ok": False, "error": "预约不存在"}
        if row.status != "pending":
            return {
                "ok": False,
                "error": f"当前状态不是 pending：{row.status}",
                "status": row.status,
            }
        lab = db.get(Lab, row.lab_id)
        user = db.get(User, row.user_id)
        prior = count_prior_approved(db, row.user_id)
        emp = (user.employee_no if user else "") or ""
        item = _dump_pending(
            row,
            lab,
            user,
            prior_approved_count=prior,
            trusted_employee=emp in load_trusted_employee_nos(),
        )

    gate = rule_gate(item)
    auto_ok = bool(gate["ok"])
    return {
        "ok": True,
        "reservation": item,
        "rule_gate": gate,
        "can_auto_approve": auto_ok,
        "hint": "规则满足，可自动通过" if auto_ok else "规则未满足，需人工确认",
    }


def _notify(db, *, user_id: int, msg_type: str, title: str, content: str, related_id: int):
    db.add(
        UserMessage(
            user_id=user_id,
            msg_type=msg_type,
            title=title,
            content=content,
            related_id=related_id,
            is_read=0,
        )
    )


def apply_decision(
    reservation_id: int,
    *,
    action: str,
    reason: str = "",
    actor_note: str = "",
) -> dict[str, Any]:
    action = (action or "").strip().lower()
    if action not in ("approve", "reject"):
        return {"ok": False, "error": "action 只能是 approve 或 reject"}

    with SyncSessionLocal() as db:
        row = db.get(Reservation, int(reservation_id))
        if not row:
            return {"ok": False, "error": "预约不存在"}
        if row.status != "pending":
            return {"ok": False, "error": f"当前状态不可审：{row.status}"}

        if action == "approve":
            row.status = "approved"
            _notify(
                db,
                user_id=row.user_id,
                msg_type="approve",
                title="预约已通过",
                content=(
                    f"预约#{row.id}已通过审核"
                    + (f"（{actor_note}）" if actor_note else "")
                    + "，请签署安全须知并领取通行码。"
                ),
                related_id=row.id,
            )
            db.commit()
            return {
                "ok": True,
                "id": row.id,
                "status": "approved",
                "message": "已通过",
            }

        why = (reason or "").strip() or "不符合实验室使用规范"
        row.status = "rejected"
        row.reject_reason = why[:300]
        _notify(
            db,
            user_id=row.user_id,
            msg_type="reject",
            title="预约已驳回",
            content=f"预约#{row.id}已被驳回。原因：{why}",
            related_id=row.id,
        )
        db.commit()
        return {
            "ok": True,
            "id": row.id,
            "status": "rejected",
            "message": "已驳回",
            "reason": why,
        }


def auto_process_pending(
    *,
    limit: int = 5,
    dry_run: bool = False,
) -> dict[str, Any]:
    """批量：仅自动通过规则闸门通过的单；其余列出待人审。不调用大模型。"""
    pending = list_pending(limit=limit)
    approved: list[dict] = []
    need_human: list[dict] = []
    skipped: list[dict] = []

    for item in pending:
        rid = int(item["id"])
        review = review_one(rid)
        if not review.get("ok"):
            skipped.append({"id": rid, "error": review.get("error")})
            continue
        if review.get("can_auto_approve"):
            if dry_run:
                approved.append(
                    {
                        "id": rid,
                        "dry_run": True,
                        "rule_gate": review.get("rule_gate"),
                    }
                )
            else:
                result = apply_decision(
                    rid,
                    action="approve",
                    actor_note="规则低风险自动通过",
                )
                approved.append({**result, "rule_gate": review.get("rule_gate")})
        else:
            need_human.append(
                {
                    "id": rid,
                    "reservation": review.get("reservation"),
                    "rule_gate": review.get("rule_gate"),
                    "hint": review.get("hint"),
                }
            )

    return {
        "dry_run": dry_run,
        "scanned": len(pending),
        "auto_approved": approved,
        "need_human": need_human,
        "skipped": skipped,
        "policy": {
            "mode": "rules_only",
            "max_hours": MAX_HOURS,
            "require_purpose": REQUIRE_PURPOSE,
            "min_history": MIN_HISTORY,
            "trusted_nos_file": str(TRUSTED_NOS_FILE),
            "eligibility": "用途合格 或 历史成功预约≥阈值 或 工号在白名单；且硬条件（时长/信用/非深夜）通过",
        },
    }
