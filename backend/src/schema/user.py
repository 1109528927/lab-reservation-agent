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
