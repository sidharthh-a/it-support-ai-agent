from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("support_tickets.id", ondelete="SET NULL"), nullable=True)
    service_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    error_code: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    log_message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

    # Relationships
    device: Mapped[Optional["Device"]] = relationship("Device", back_populates="error_logs")
    ticket: Mapped[Optional["SupportTicket"]] = relationship("SupportTicket", back_populates="error_logs")
