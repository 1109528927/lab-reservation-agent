
import traceback

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

DEBUG_MODE = True  # 教学项目保持开启

_FIELD_LABELS = {
    "username": "账号",
    "password": "密码",
    "repassword": "确认密码",
    "employee_no": "学号/工号",
    "role": "角色",
}


def _format_validation_message(exc: RequestValidationError) -> str:
    """把 Pydantic 422 英文明细收成一句中文。"""
    messages: list[str] = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x != "body"]
        field = loc[-1] if loc else "参数"
        label = _FIELD_LABELS.get(field, field)
        etype = err.get("type", "")
        ctx = err.get("ctx") or {}

        if etype == "missing":
            messages.append(f"{label}不能为空")
        elif etype == "string_too_short":
            min_len = ctx.get("min_length")
            if min_len:
                messages.append(f"{label}至少 {min_len} 个字符")
            else:
                messages.append(f"{label}太短")
        elif etype == "string_too_long":
            max_len = ctx.get("max_length")
            if max_len:
                messages.append(f"{label}不能超过 {max_len} 个字符")
            else:
                messages.append(f"{label}太长")
        elif etype.startswith("value_error"):
            # 自定义 ValueError（如两次密码不一致）已是中文
            msg = err.get("msg", "")
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, ") :]
            messages.append(msg or f"{label}不合法")
        else:
            msg = err.get("msg", "参数错误")
            messages.append(f"{label}：{msg}")

    return "；".join(messages) if messages else "请求参数不正确"


async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": 422,
            "message": _format_validation_message(exc),
            "data": exc.errors() if DEBUG_MODE else None,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    # HTTPException 通常是业务逻辑主动抛出的，data 保持 None
    detail = exc.detail
    if isinstance(detail, list):
        # 极少数情况 detail 仍是校验列表
        detail = "请求参数不正确"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": detail,
            "data": None,
        },
    )
async def integrity_error_handler(request: Request, exc: IntegrityError):
    error_msg = str(exc.orig)

    if "username_UNIQUE" in error_msg or "Duplicate entry" in error_msg:
        detail = "用户名已存在"
    elif "FOREIGN KEY" in error_msg:
        detail = "关联数据不存在"
    else:
        detail = "数据约束冲突，请检查输入"

    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": "IntegrityError",
            "error_detail": error_msg,
            "path": str(request.url),
        }

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"code": 400, "message": detail, "data": error_data},
    )
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": type(exc).__name__,
            "error_detail": str(exc),
            "traceback": traceback.format_exc(),  # 堆栈字符串，方便调试
            "path": str(request.url),
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "数据库操作失败，请稍后重试",
            "data": error_data,
        },
    )

async def general_exception_handler(request: Request, exc: Exception):
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": type(exc).__name__,
            "error_detail": str(exc),
            "traceback": traceback.format_exc(),
            "path": str(request.url),
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": error_data,
        },
    )

def register_exception_handlers(app):
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)  # 业务
    app.add_exception_handler(IntegrityError, integrity_error_handler)  # 数据完整性约束
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)  # 数据库
    app.add_exception_handler(Exception, general_exception_handler)  # 兜底