from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", index=True, nullable=False)  # open, in_progress, resolved, closed, escalated
    priority: Mapped[str] = mapped_column(String(50), default="medium", index=True, nullable=False)  # low, medium, high, critical
    category: Mapped[str] = mapped_column(String(100), default="software", index=True, nullable=False)  # network, hardware, software, access, security
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="tickets_created")
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to_id], back_populates="tickets_assigned")
    device: Mapped[Optional["Device"]] = relationship("Device", back_populates="tickets")
    
    incidents: Mapped[List["Incident"]] = relationship("Incident", back_populates="ticket")
    error_logs: Mapped[List["ErrorLog"]] = relationship("ErrorLog", back_populates="ticket")
    resolution: Mapped[Optional["Resolution"]] = relationship("Resolution", back_populates="ticket", uselist=False)
    history: Mapped[List["TicketHistory"]] = relationship("TicketHistory", back_populates="ticket", cascade="all, delete-orphan")
    comments: Mapped[List["TicketComment"]] = relationship(
        "TicketComment", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketComment.created_at"
    )
