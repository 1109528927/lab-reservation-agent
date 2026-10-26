from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ReservationCreate(BaseModel):
    lab_id: int
    start_time: datetime
    end_time: datetime
    purpose: Optional[str] = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def check_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class ReservationOut(BaseModel):
    id: int
    lab_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: str
    purpose: Optional[str] = None
    reject_reason: Optional[str] = None
    create_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RejectIn(BaseModel):
    reason: str = Field(default="不符合开放安排", max_length=300)
