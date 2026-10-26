from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from model.user import Base


class SafetyAck(Base):
    __tablename__ = "safety_ack"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    reservation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reservation.id"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")


class Passcode(Base):
    __tablename__ = "passcode"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    reservation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reservation.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AccessLog(Base):
    __tablename__ = "access_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reservation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
