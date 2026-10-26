from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SafetyAckIn(BaseModel):
    reservation_id: int


class PasscodeIssueIn(BaseModel):
    reservation_id: int


class PasscodeOut(BaseModel):
    id: int
    code: str
    reservation_id: int
    user_id: int
    status: str
    valid_from: datetime
    valid_to: datetime
    # 展示用：成功刷码次数（不废码，有效期内可多次）
    scan_ok_count: int = 0
    last_allowed_at: Optional[datetime] = None
    # 领码弹窗：实验室与时段
    lab_id: Optional[int] = None
    lab_name: Optional[str] = None
    lab_location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    model_config = {"from_attributes": True}


class VerifyIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    device_id: str = Field(default="SIM-DOOR-01", max_length=64)


class AccessLogOut(BaseModel):
    id: int
    code: Optional[str] = None
    device_id: Optional[str] = None
    user_id: Optional[int] = None
    reservation_id: Optional[int] = None
    allowed: int
    reason: Optional[str] = None
    create_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
