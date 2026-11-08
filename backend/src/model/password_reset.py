"""忘记密码申请。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from model.user import Base


class PasswordResetRequest(Base):
    __tablename__ = "password_reset_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    employee_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    handler_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    admin_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    create_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
