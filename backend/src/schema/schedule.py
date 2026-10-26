from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScheduleBlockCreate(BaseModel):
    lab_id: int
    title: str = Field(min_length=1, max_length=200)
    start_time: datetime
    end_time: datetime
    note: Optional[str] = Field(default=None, max_length=300)


class ScheduleBlockOut(BaseModel):
    id: int
    lab_id: int
    title: str
    start_time: datetime
    end_time: datetime
    source: str
    created_by: Optional[int] = None
    note: Optional[str] = None

    model_config = {"from_attributes": True}
