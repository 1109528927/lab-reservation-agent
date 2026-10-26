"""站内消息、信用、报修、定时业务 tick。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.request import get_db
from crud import lab as lab_crud
from crud import ops as ops_crud
from model.user import User
from schema.ops import (
    CreditLogOut,
    MessageOut,
    RepairCreate,
    RepairOut,
    RepairUpdate,
)
from utils.auth import get_current_user
from utils.response import success_response
from utils.roles import require_school_admin

router = APIRouter(prefix="/api", tags=["ops"])


def _msg(row) -> dict:
    return MessageOut.model_validate(row).model_dump()


def _repair(row) -> dict:
    return RepairOut.model_validate(row).model_dump()


@router.post("/ops/tick")
async def ops_tick(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """扫描爽约与通行码过期提醒。登录用户可触发，便于演示。"""
    _ = user
    result = await ops_crud.run_ops_tick(db)
    return success_response(message="业务扫描完成", data=result)


@router.get("/messages")
async def my_messages(
    only_unread: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 打开消息列表时顺带跑一遍提醒/爽约，保证闭环可演示
    await ops_crud.run_ops_tick(db)
    rows = await ops_crud.list_messages(db, user.id, only_unread=only_unread)
    unread = await ops_crud.unread_count(db, user.id)
    return success_response(
        message="ok",
        data={"items": [_msg(x) for x in rows], "unread": unread},
    )


@router.get("/messages/unread-count")
async def messages_unread(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = await ops_crud.unread_count(db, user.id)
    return success_response(message="ok", data={"unread": n})


@router.post("/messages/{msg_id}/read")
async def read_message(
    msg_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = await ops_crud.mark_read(db, user.id, msg_id)
    if not row:
        raise HTTPException(status_code=404, detail="消息不存在")
    await db.commit()
    return success_response(message="已读", data=_msg(row))


@router.post("/messages/read-all")
async def read_all_messages(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = await ops_crud.mark_all_read(db, user.id)
    await db.commit()
    return success_response(message=f"已读 {n} 条", data={"count": n})


@router.get("/credit/me")
async def my_credit(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    logs = await ops_crud.list_credit_logs(db, user.id)
    return success_response(
        message="ok",
        data={
            "credit_score": user.credit_score,
            "min_to_reserve": ops_crud.CREDIT_MIN_TO_RESERVE,
            "deduct_no_show": ops_crud.CREDIT_DEDUCT_NO_SHOW,
            "logs": [CreditLogOut.model_validate(x).model_dump() for x in logs],
        },
    )


@router.get("/credit/users")
async def credit_users(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    rows = await ops_crud.list_users_credit(db)
    return success_response(
        message="ok",
        data={
            "items": [
                {
                    "id": u.id,
                    "username": u.username,
                    "employee_no": u.employee_no,
                    "role": u.role,
                    "credit_score": u.credit_score,
                }
                for u in rows
            ],
            "min_to_reserve": ops_crud.CREDIT_MIN_TO_RESERVE,
        },
    )


@router.get("/credit/users/{uid}/logs")
async def credit_user_logs(
    uid: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    logs = await ops_crud.list_credit_logs(db, uid)
    return success_response(
        message="ok",
        data={"items": [CreditLogOut.model_validate(x).model_dump() for x in logs]},
    )


@router.post("/repairs")
async def create_repair(
    body: RepairCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lab = await lab_crud.get_lab(db, body.lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="实验室不存在")
    row = await ops_crud.create_repair(
        db,
        lab_id=body.lab_id,
        user_id=user.id,
        title=body.title.strip(),
        description=(body.description or "").strip() or None,
    )
    # 通知管理员：写入各 admin 消息
    from sqlalchemy import select

    admins = list(
        (await db.execute(select(User).where(User.role == "admin"))).scalars().all()
    )
    for a in admins:
        await ops_crud.create_message(
            db,
            user_id=a.id,
            msg_type="repair",
            title="新报修工单",
            content=f"用户 {user.username} 对实验室「{lab.name}」提交报修：{row.title}",
            related_id=row.id,
        )
    await db.commit()
    await db.refresh(row)
    return success_response(message="报修已提交", data=_repair(row))


@router.get("/repairs/mine")
async def my_repairs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = await ops_crud.list_repairs_by_user(db, user.id)
    return success_response(message="ok", data={"items": [_repair(x) for x in rows]})


@router.get("/repairs")
async def list_repairs(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    rows = await ops_crud.list_repairs_all(db, status=status)
    return success_response(message="ok", data={"items": [_repair(x) for x in rows]})


@router.post("/repairs/{ticket_id}/update")
async def update_repair(
    ticket_id: int,
    body: RepairUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    if body.status not in ("pending", "processing", "done"):
        raise HTTPException(status_code=400, detail="状态仅支持 pending/processing/done")
    row = await ops_crud.get_repair(db, ticket_id)
    if not row:
        raise HTTPException(status_code=404, detail="工单不存在")
    row.status = body.status
    row.handler_id = user.id
    if body.admin_reply is not None:
        row.admin_reply = body.admin_reply.strip() or None
    await db.flush()
    status_cn = {"pending": "待处理", "processing": "处理中", "done": "已完成"}[body.status]
    await ops_crud.create_message(
        db,
        user_id=row.user_id,
        msg_type="repair",
        title=f"报修工单已更新为{status_cn}",
        content=(
            f"工单#{row.id}「{row.title}」状态：{status_cn}。"
            + (f" 管理员回复：{row.admin_reply}" if row.admin_reply else "")
        ),
        related_id=row.id,
    )
    await db.commit()
    await db.refresh(row)
    return success_response(message="工单已更新", data=_repair(row))
