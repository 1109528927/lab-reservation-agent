from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from model.user import Base


class LabScheduleBlock(Base):
    """教务排课占档：挡预约，不走审批/通行码。"""

    __tablename__ = "lab_schedule_block"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    create_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
