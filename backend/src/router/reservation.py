"""预约路由（A1）：冲突检测 + 审批。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.request import get_db
from crud import access as access_crud
from crud import lab as lab_crud
from crud import ops as ops_crud
from crud import reservation as res_crud
from model.user import User
from schema.reservation import RejectIn, ReservationCreate, ReservationOut
from utils.auth import get_current_user
from utils.response import success_response
from utils.roles import require_school_admin, reservation_status_for_role

router = APIRouter(prefix="/api/reservations", tags=["reservations"])


def _dump(row) -> dict:
    return ReservationOut.model_validate(row).model_dump()


@router.post("")
async def create_reservation(
    body: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    score = int(user.credit_score or 100)
    if score < ops_crud.CREDIT_MIN_TO_RESERVE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"信用分不足：当前{score}分，"
                f"低于{ops_crud.CREDIT_MIN_TO_RESERVE}分不可新预约"
            ),
        )

    lab = await lab_crud.get_lab(db, body.lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="实验室不存在")
    if lab.status != "open":
        raise HTTPException(status_code=400, detail="实验室未开放预约")

    conflict = await res_crud.find_conflict(
        db,
        lab_id=body.lab_id,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    if conflict:
        raise HTTPException(
            status_code=400,
            detail=f"时段冲突：已有预约 #{conflict.id}（{conflict.start_time} ~ {conflict.end_time}）",
        )

    block = await res_crud.find_schedule_conflict(
        db,
        lab_id=body.lab_id,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    if block:
        raise HTTPException(
            status_code=400,
            detail=(
                f"与排课《{block.title}》冲突"
                f"（{block.start_time} ~ {block.end_time}）"
            ),
        )

    status = reservation_status_for_role(user.role)
    row = await res_crud.create_reservation(
        db,
        lab_id=body.lab_id,
        user_id=user.id,
        start_time=body.start_time,
        end_time=body.end_time,
        purpose=body.purpose,
        status=status,
    )
    if status == "approved":
        await ops_crud.create_message(
            db,
            user_id=user.id,
            msg_type="approve",
            title="预约已通过",
            content=f"预约#{row.id}已通过，请签署安全须知并领取通行码。",
            related_id=row.id,
        )
        await db.commit()
    msg = (
        "预约已提交，等待管理员审核"
        if status == "pending"
        else "预约已通过（老师/管理员可直接预约）"
    )
    return success_response(message=msg, data=_dump(row))



@router.get("/mine")
async def my_reservations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = await res_crud.list_by_user(db, user.id)
    return success_response(message="ok", data={"items": [_dump(x) for x in rows]})


@router.get("")
async def list_reservations(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    rows = await res_crud.list_all(db, status=status)
    return success_response(message="ok", data={"items": [_dump(x) for x in rows]})


@router.post("/{res_id}/approve")
async def approve(
    res_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    row = await res_crud.get_reservation(db, res_id)
    if not row:
        raise HTTPException(status_code=404, detail="预约不存在")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail=f"当前状态不可审批：{row.status}")
    row.status = "approved"
    await db.flush()
    await ops_crud.create_message(
        db,
        user_id=row.user_id,
        msg_type="approve",
        title="预约已通过",
        content=f"预约#{row.id}已通过审核，请签署安全须知并领取通行码。",
        related_id=row.id,
    )
    await db.commit()
    await db.refresh(row)
    return success_response(message="已通过", data=_dump(row))


@router.post("/{res_id}/reject")
async def reject(
    res_id: int,
    body: RejectIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    row = await res_crud.get_reservation(db, res_id)
    if not row:
        raise HTTPException(status_code=404, detail="预约不存在")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail=f"当前状态不可驳回：{row.status}")

    row.status = "rejected"
    row.reject_reason = body.reason
    await db.flush()
    await access_crud.revoke_passcodes_for_reservation(db, row.id)
    reason = (body.reason or "").strip() or "未填写原因"
    await ops_crud.create_message(
        db,
        user_id=row.user_id,
        msg_type="reject",
        title="预约已驳回",
        content=f"预约#{row.id}已被驳回。原因：{reason}",
        related_id=row.id,
    )
    await db.commit()
    await db.refresh(row)
    return success_response(message="已驳回", data=_dump(row))


@router.post("/{res_id}/cancel")
async def cancel(
    res_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = await res_crud.get_reservation(db, res_id)
    if not row:
        raise HTTPException(status_code=404, detail="预约不存在")
    if row.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="只能取消自己的预约")

    if row.status not in ("pending", "approved", "in_use"):
        raise HTTPException(status_code=400, detail=f"当前状态不可取消：{row.status}")
    row.status = "cancelled"
    await db.flush()
    await db.commit()
    await access_crud.revoke_passcodes_for_reservation(db, row.id)
    await db.refresh(row)
    return success_response(message="已取消", data=_dump(row))
