from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: int
    user_id: int
    msg_type: str
    title: str
    content: str
    related_id: Optional[int] = None
    is_read: int
    create_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreditLogOut(BaseModel):
    id: int
    user_id: int
    delta: int
    score_after: int
    reason: str
    reservation_id: Optional[int] = None
    create_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RepairCreate(BaseModel):
    lab_id: int
    title: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class RepairUpdate(BaseModel):
    status: str = Field(description="pending/processing/done")
    admin_reply: Optional[str] = Field(default=None, max_length=500)


class RepairOut(BaseModel):
    id: int
    lab_id: int
    user_id: int
    title: str
    description: Optional[str] = None
    status: str
    admin_reply: Optional[str] = None
    handler_id: Optional[int] = None
    create_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
