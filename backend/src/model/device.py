from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from model.user import Base


class AccessDevice(Base):
    __tablename__ = "access_device"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    lab_id: Mapped[int] = mapped_column(Integer, ForeignKey("lab.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
