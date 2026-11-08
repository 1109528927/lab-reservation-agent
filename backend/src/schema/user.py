from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class RegisterIn(BaseModel):
    username: str = Field(min_length=1, max_length=50, description="账号")
    password: str = Field(min_length=6, max_length=128, description="密码")
    repassword: str = Field(min_length=6, max_length=128, description="确认密码")
    employee_no: Optional[str] = Field(default=None, max_length=50, description="学号/工号")
    # 兼容旧客户端字段；服务端一律忽略，强制 student
    role: Optional[str] = Field(default=None, max_length=20, description="已废弃，忽略")

    @field_validator("username", "password", "repassword")
    @classmethod
    def strip_text(cls, v: str):
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise ValueError("不能为空")
        return v

    @field_validator("repassword")
    @classmethod
    def passwords_match(cls, v: str, info):
        password = info.data.get("password")
        if password is not None and v != password:
            raise ValueError("两次密码不一致")
        return v



class UserOut(BaseModel):
    id: int
    username: str
    employee_no: str
    role: str
    credit_score: Optional[int] = 100
    create_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LoginOut(BaseModel):
    token: str
    expires_at: datetime
    user: UserOut


class AdminCreateStudentIn(BaseModel):
    """管理端：单个开通学生（可自定义账号与密码）。"""

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    employee_no: Optional[str] = Field(
        default=None,
        max_length=50,
        description="学号；空则默认与账号相同",
    )

    @field_validator("username", "password")
    @classmethod
    def strip_create(cls, v: str):
        v = v.strip()
        if not v:
            raise ValueError("不能为空")
        return v

    @field_validator("employee_no")
    @classmethod
    def strip_eno(cls, v: Optional[str]):
        if v is None:
            return None
        v = v.strip()
        return v or None


class AdminUpdateStudentIn(BaseModel):
    """管理端：修改学生学号和/或重置密码。"""

    employee_no: Optional[str] = Field(default=None, max_length=50)
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)

    @field_validator("employee_no", "password")
    @classmethod
    def strip_update(cls, v: Optional[str]):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class BulkStudentsIn(BaseModel):
    """管理端：按学号清单批量开通学生账号。"""

    employee_nos: str = Field(
        ...,
        min_length=1,
        description="学号清单，支持换行/逗号/分号/空白分隔",
    )
    default_password: str = Field(
        default="Lab@123456",
        min_length=6,
        max_length=128,
        description="统一初始密码",
    )

    @field_validator("employee_nos", "default_password")
    @classmethod
    def strip_bulk(cls, v: str):
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise ValueError("不能为空")
        return v


class BulkStudentItemOut(BaseModel):
    employee_no: str
    username: str | None = None
    status: str  # created | skipped | failed
    reason: str | None = None


class BulkStudentsOut(BaseModel):
    total: int
    created: int
    skipped: int
    failed: int
    default_password: str
    items: list[BulkStudentItemOut]


class PasswordHelpOut(BaseModel):
    admin_qq_email: str
    tip: str


class ForgotPasswordIn(BaseModel):
    username: str = Field(min_length=1, max_length=50, description="登录账号")
    employee_no: Optional[str] = Field(default=None, max_length=50)
    contact: Optional[str] = Field(
        default=None, max_length=120, description="联系方式（手机/QQ等）"
    )
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str):
        v = v.strip()
        if not v:
            raise ValueError("不能为空")
        return v

    @field_validator("employee_no", "contact", "reason")
    @classmethod
    def strip_opt(cls, v: Optional[str]):
        if v is None:
            return None
        v = v.strip()
        return v or None


class PasswordResetRequestOut(BaseModel):
    id: int
    username: str
    employee_no: Optional[str] = None
    contact: Optional[str] = None
    reason: Optional[str] = None
    status: str
    handler_id: Optional[int] = None
    admin_note: Optional[str] = None
    create_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ResolvePasswordResetIn(BaseModel):
    action: str = Field(description="done | rejected")
    admin_note: Optional[str] = Field(default=None, max_length=500)
    new_password: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=128,
        description="action=done 时可填，重置该账号密码",
    )

    @field_validator("action")
    @classmethod
    def check_action(cls, v: str):
        v = (v or "").strip()
        if v not in ("done", "rejected"):
            raise ValueError("action 只能是 done 或 rejected")
        return v
