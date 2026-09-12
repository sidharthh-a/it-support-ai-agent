from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    os: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, maintenance, retired
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="devices")
    tickets: Mapped[List["SupportTicket"]] = relationship("SupportTicket", back_populates="device")
    error_logs: Mapped[List["ErrorLog"]] = relationship("ErrorLog", back_populates="device")
