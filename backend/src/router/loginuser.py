import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.request import get_db
from crud import password_reset as pwd_crud
from crud.user import (
    add_user,
    bulk_create_students,
    create_token,
    get_user_by_employee_no,
    get_user_by_id,
    get_user_by_username,
    list_students,
    parse_employee_no_list,
    update_student,
)
from model.user import User
from schema.user import (
    AdminCreateStudentIn,
    AdminUpdateStudentIn,
    BulkStudentsIn,
    BulkStudentsOut,
    ForgotPasswordIn,
    LoginIn,
    LoginOut,
    PasswordHelpOut,
    PasswordResetRequestOut,
    RegisterIn,
    ResolvePasswordResetIn,
    UserOut,
)
from utils.auth import get_current_user
from utils.response import success_response
from utils.roles import require_school_admin
from utils.security import verify_password


def _admin_qq_email() -> str:
    return (
        os.getenv("ADMIN_QQ_EMAIL", "").strip()
        or "admin@qq.com"
    )

router = APIRouter(prefix="/api/user", tags=["user"])


@router.post("/register")
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    if await get_user_by_username(db, body.username):
        raise HTTPException(status_code=400, detail="用户名已存在")

    employee_no = (body.employee_no or "").strip() or f"U{uuid4().hex[:8]}"
    if await get_user_by_employee_no(db, employee_no):
        raise HTTPException(status_code=400, detail="工号/学号已存在")

    # 公开注册只能学生；老师/管理员由学校侧建号，禁止自提权
    if body.role and body.role != "student":
        raise HTTPException(status_code=400, detail="公开注册仅支持学生角色")

    user = await add_user(
        db,
        username=body.username,
        password=body.password,
        employee_no=employee_no,
        role="student",
    )

    return success_response(
        message="注册成功",
        data=UserOut.model_validate(user).model_dump(),
    )


@router.post("/login")
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_username(db, body.username)
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    token_row = await create_token(db, user.id)
    payload = LoginOut(
        token=token_row.token,
        expires_at=token_row.expires_at,
        user=UserOut.model_validate(user),
    )
    return success_response(message="登录成功", data=payload.model_dump())


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return success_response(
        message="ok",
        data=UserOut.model_validate(user).model_dump(),
    )


@router.get("/password-help")
async def password_help():
    """登录页展示：管理员 QQ 邮箱（无需登录）。"""
    email = _admin_qq_email()
    tip = (
        f"无法登录时可向管理员 QQ 邮箱 {email} 说明账号，"
        "或在本页提交找回申请，管理员处理后会重置密码。"
    )
    return success_response(
        message="ok",
        data=PasswordHelpOut(admin_qq_email=email, tip=tip).model_dump(),
    )


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordIn, db: AsyncSession = Depends(get_db)):
    """公开：提交忘记密码申请（不发真实邮件，落库并通知管理员站内信）。"""
    row = await pwd_crud.create_request(
        db,
        username=body.username,
        employee_no=body.employee_no,
        contact=body.contact,
        reason=body.reason,
    )
    return success_response(
        message=f"申请已提交，请等待管理员处理；也可邮件联系 {_admin_qq_email()}",
        data=PasswordResetRequestOut.model_validate(row).model_dump(),
    )


@router.get("/admin/password-requests")
async def admin_list_password_requests(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    rows = await pwd_crud.list_requests(db, status=status)
    return success_response(
        message="ok",
        data={
            "admin_qq_email": _admin_qq_email(),
            "items": [
                PasswordResetRequestOut.model_validate(r).model_dump() for r in rows
            ],
        },
    )


@router.post("/admin/password-requests/{req_id}/resolve")
async def admin_resolve_password_request(
    req_id: int,
    body: ResolvePasswordResetIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    row = await pwd_crud.get_request(db, req_id)
    if not row:
        raise HTTPException(status_code=404, detail="申请不存在")
    result = await pwd_crud.resolve_request(
        db,
        row=row,
        handler_id=user.id,
        action=body.action,
        admin_note=body.admin_note,
        new_password=body.new_password,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("detail") or "处理失败")
    return success_response(
        message="已处理"
        + (
            f"：已重置账号 {result['reset_username']} 的密码"
            if result.get("reset_username")
            else ""
        ),
        data={
            "request": PasswordResetRequestOut.model_validate(row).model_dump(),
            **result,
        },
    )


@router.get("/admin/students")
async def admin_list_students(
    q: str | None = Query(default=None, description="账号或学号模糊搜索"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_school_admin(user)
    rows = await list_students(db, q=q)
    return success_response(
        message="ok",
        data={"items": [UserOut.model_validate(r).model_dump() for r in rows]},
    )


@router.post("/admin/students")
async def admin_create_student(
    body: AdminCreateStudentIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """单个开通：自定义账号 + 密码 + 学号。"""
    require_school_admin(user)
    if await get_user_by_username(db, body.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    employee_no = body.employee_no or body.username
    if await get_user_by_employee_no(db, employee_no):
        raise HTTPException(status_code=400, detail="学号已存在")
    row = await add_user(
        db,
        username=body.username,
        password=body.password,
        employee_no=employee_no,
        role="student",
    )
    return success_response(
        message="学生账号已创建",
        data=UserOut.model_validate(row).model_dump(),
    )


@router.put("/admin/students/{user_id}")
async def admin_update_student(
    user_id: int,
    body: AdminUpdateStudentIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """修改学号和/或重置密码（仅学生）。"""
    require_school_admin(user)
    if body.employee_no is None and body.password is None:
        raise HTTPException(status_code=400, detail="请至少修改学号或密码一项")
    target = await get_user_by_id(db, user_id)
    if not target or target.role != "student":
        raise HTTPException(status_code=404, detail="学生不存在")
    try:
        row = await update_student(
            db,
            target,
            employee_no=body.employee_no,
            password=body.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return success_response(
        message="已更新",
        data=UserOut.model_validate(row).model_dump(),
    )


@router.post("/admin/bulk-students")
async def admin_bulk_students(
    body: BulkStudentsIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """学校管理员：粘贴学号清单，一键开通学生账号（学号=登录名，统一初始密码）。"""
    require_school_admin(user)
    nos = parse_employee_no_list(body.employee_nos)
    if not nos:
        raise HTTPException(status_code=400, detail="未解析到有效学号")
    if len(nos) > 500:
        raise HTTPException(status_code=400, detail="单次最多 500 个学号，请分批导入")

    items = await bulk_create_students(
        db,
        employee_nos=nos,
        default_password=body.default_password,
    )
    created = sum(1 for x in items if x["status"] == "created")
    skipped = sum(1 for x in items if x["status"] == "skipped")
    failed = sum(1 for x in items if x["status"] == "failed")
    payload = BulkStudentsOut(
        total=len(items),
        created=created,
        skipped=skipped,
        failed=failed,
        default_password=body.default_password,
        items=items,
    )
    return success_response(
        message=f"完成：新建 {created}，跳过 {skipped}，失败 {failed}",
        data=payload.model_dump(),
    )
