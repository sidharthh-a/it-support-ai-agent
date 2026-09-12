from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="P3", index=True, nullable=False)  # P1, P2, P3, P4
    status: Mapped[str] = mapped_column(String(50), default="investigating", index=True, nullable=False)  # investigating, identified, monitoring, resolved
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("support_tickets.id", ondelete="SET NULL"), nullable=True)
    affected_service: Mapped[str] = mapped_column(String(100), nullable=False)
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    ticket: Mapped[Optional["SupportTicket"]] = relationship("SupportTicket", back_populates="incidents")
