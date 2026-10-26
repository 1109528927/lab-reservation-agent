from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LabCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    location: Optional[str] = Field(default=None, max_length=200)
    capacity: int = Field(default=20, ge=1, le=500)
    need_approve: int = Field(default=1, ge=0, le=1)
    status: str = Field(default="open", max_length=20)
    description: Optional[str] = Field(default=None, max_length=500)


class LabUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    location: Optional[str] = Field(default=None, max_length=200)
    capacity: Optional[int] = Field(default=None, ge=1, le=500)
    need_approve: Optional[int] = Field(default=None, ge=0, le=1)
    status: Optional[str] = Field(default=None, max_length=20)
    description: Optional[str] = Field(default=None, max_length=500)


class LabOut(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    capacity: int
    need_approve: int
    status: str
    description: Optional[str] = None
    create_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
