"""实验室路由（A1）。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.request import get_db
from crud import lab as lab_crud
from crud import reservation as res_crud
from crud import schedule as schedule_crud
from model.user import User
from schema.lab import LabCreate, LabOut, LabUpdate
from utils.auth import get_current_user
from utils.response import success_response
from utils.roles import require_admin

router = APIRouter(prefix="/api/labs", tags=["labs"])


@router.get("")
async def list_labs(
    only_open: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ = user
    rows = await lab_crud.list_labs(db, only_open=only_open)
    return success_response(
        message="ok",
        data={"items": [LabOut.model_validate(x).model_dump() for x in rows]},
    )


@router.get("/{lab_id}/day-occupancy")
async def day_occupancy(
    lab_id: int,
    date: str = Query(..., description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """某实验室某日：排课占档 + 活跃预约（预约前看占用）。"""
    _ = user
    lab = await lab_crud.get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="实验室不存在")
    try:
        day = datetime.strptime(date[:10], "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="日期格式须为 YYYY-MM-DD") from e
    day_end = day + timedelta(days=1)
    blocks = await schedule_crud.list_blocks(
        db, lab_id=lab_id, start=day, end=day_end
    )
    reservations = await res_crud.list_active_on_day(
        db, lab_id=lab_id, day_start=day, day_end=day_end
    )
    return success_response(
        message="ok",
        data={
            "date": date[:10],
            "lab_id": lab_id,
            "lab_name": lab.name,
            "schedule": [
                {
                    "id": b.id,
                    "kind": "schedule",
                    "title": b.title,
                    "start_time": b.start_time,
                    "end_time": b.end_time,
                    "note": b.note,
                }
                for b in blocks
            ],
            "reservations": [
                {
                    "id": r.id,
                    "kind": "reservation",
                    "title": r.purpose or f"预约#{r.id}",
                    "status": r.status,
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                }
                for r in reservations
            ],
        },
    )


@router.get("/{lab_id}")
async def get_lab(
    lab_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ = user
    lab = await lab_crud.get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="实验室不存在")
    return success_response(message="ok", data=LabOut.model_validate(lab).model_dump())



@router.post("")
async def create_lab(
    body: LabCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    if await lab_crud.get_lab_by_name(db, body.name.strip()):
        raise HTTPException(status_code=400, detail="实验室名称已存在")
    lab = await lab_crud.create_lab(
        db,
        name=body.name.strip(),
        location=body.location,
        capacity=body.capacity,
        need_approve=body.need_approve,
        status=body.status,
        description=body.description,
    )
    return success_response(
        message="创建成功",
        data=LabOut.model_validate(lab).model_dump(),
    )


@router.put("/{lab_id}")
async def update_lab(
    lab_id: int,
    body: LabUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    lab = await lab_crud.get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="实验室不存在")
    if body.name and body.name.strip() != lab.name:
        if await lab_crud.get_lab_by_name(db, body.name.strip()):
            raise HTTPException(status_code=400, detail="实验室名称已存在")
    payload = body.model_dump(exclude_unset=True)
    if "name" in payload and payload["name"]:
        payload["name"] = payload["name"].strip()
    lab = await lab_crud.update_lab(db, lab, **payload)
    return success_response(
        message="更新成功",
        data=LabOut.model_validate(lab).model_dump(),
    )
