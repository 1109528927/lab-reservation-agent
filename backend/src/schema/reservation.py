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
        from crud.reservation import assert_not_past_range

        err = assert_not_past_range(self.start_time, self.end_time)
        if err:
            raise ValueError(err)
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
