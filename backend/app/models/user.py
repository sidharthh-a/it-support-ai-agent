from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="employee", nullable=False)  # admin, support, employee
    department: Mapped[str] = mapped_column(String(100), default="General", nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    tickets_created: Mapped[List["SupportTicket"]] = relationship(
        "SupportTicket", foreign_keys="SupportTicket.user_id", back_populates="creator"
    )
    tickets_assigned: Mapped[List["SupportTicket"]] = relationship(
        "SupportTicket", foreign_keys="SupportTicket.assigned_to_id", back_populates="assignee"
    )
    devices: Mapped[List["Device"]] = relationship("Device", back_populates="user")
    ticket_histories: Mapped[List["TicketHistory"]] = relationship("TicketHistory", back_populates="changed_by")
    resolutions: Mapped[List["Resolution"]] = relationship("Resolution", back_populates="resolved_by")
