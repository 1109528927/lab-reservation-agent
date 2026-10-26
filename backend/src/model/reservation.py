from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from model.user import Base


class Reservation(Base):
    __tablename__ = "reservation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey("lab.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    purpose: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
