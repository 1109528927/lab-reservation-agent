"""排课占档：仅学校管理员写；登录用户可读日历。"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from config.request import SyncSessionLocal, get_db
from crud import lab as lab_crud
from crud import reservation as res_crud
from crud import schedule as schedule_crud
from model.schedule import LabScheduleBlock
from model.user import User
from schema.schedule import ScheduleBlockCreate, ScheduleBlockOut
from utils.auth import get_current_user
from utils.response import success_response
from utils.roles import require_school_admin

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


def _dump(row) -> dict:
    return ScheduleBlockOut.model_validate(row).model_dump()


@router.get("/blocks")
async def list_blocks(
    from_time: datetime = Query(alias="from"),
    to_time: datetime = Query(alias="to"),
    lab_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ = user
    if to_time <= from_time:
        raise HTTPException(status_code=400, detail="to 须晚于 from")
    rows = await schedule_crud.list_blocks(
        db, lab_id=lab_id, start=from_time, end=to_time
    )
    return success_response(message="ok", data={"items": [_dump(x) for x in rows]})


@router.post("/blocks")
async def create_block(
    body: ScheduleBlockCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    lab = await lab_crud.get_lab(db, body.lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="实验室不存在")
    if body.end_time <= body.start_time:
        raise HTTPException(status_code=400, detail="结束时间须晚于开始时间")
    overlap = await res_crud.find_schedule_conflict(
        db,
        lab_id=body.lab_id,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    if overlap:
        raise HTTPException(
            status_code=400,
            detail=f"与已有排课《{overlap.title}》重叠",
        )
    row = await schedule_crud.create_block(
        db,
        lab_id=body.lab_id,
        title=body.title.strip(),
        start_time=body.start_time,
        end_time=body.end_time,
        source="manual",
        created_by=user.id,
        note=body.note,
    )
    return success_response(message="已添加排课", data=_dump(row))


@router.delete("/blocks/{block_id}")
async def delete_block(
    block_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    row = await schedule_crud.get_block(db, block_id)
    if not row:
        raise HTTPException(status_code=404, detail="排课不存在")
    await schedule_crud.delete_block(db, row)
    return success_response(message="已删除")


@router.get("/template.xlsx")
async def download_template(user: User = Depends(get_current_user)):
    require_school_admin(user)
    data = schedule_crud.build_template_bytes()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="lab_schedule_template.xlsx"'
        },
    )


@router.post("/import")
async def import_schedule(
    file: UploadFile = File(...),
    commit: bool = Query(default=False, description="false=仅预览，true=写入"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    _ = db
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="空文件")

    with SyncSessionLocal() as session:
        result = schedule_crud.parse_excel_preview(
            session, content, created_by=user.id, source="excel"
        )
        preview = {
            "ok_rows": result["ok_rows"],
            "block_count": result["block_count"],
            "skipped_count": result.get("skipped_count", 0),
            "skipped": result.get("skipped") or [],
            "errors": result["errors"],
            "sample": [
                {
                    "lab_id": b["lab_id"],
                    "title": b["title"],
                    "start_time": str(b["start_time"]),
                    "end_time": str(b["end_time"]),
                    "note": b.get("note"),
                }
                for b in result["blocks"][:8]
            ],
        }

        if not commit:
            return success_response(message="预览完成", data=preview)

        if result["errors"] and not result["blocks"]:
            raise HTTPException(status_code=400, detail="无可导入数据，请先修正错误行")

        for b in result["blocks"]:
            session.add(LabScheduleBlock(**b))
        session.commit()

        preview["committed"] = True
        return success_response(
            message=f"已导入 {result['block_count']} 条排课",
            data=preview,
        )
