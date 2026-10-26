"""站内消息、信用流水、报修工单。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from model.user import Base


class UserMessage(Base):
    __tablename__ = "user_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    msg_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class CreditLog(Base):
    __tablename__ = "credit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    score_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    reservation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class RepairTicket(Base):
    __tablename__ = "repair_ticket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey("lab.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    admin_reply: Mapped[str | None] = mapped_column(String(500), nullable=True)
    handler_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
