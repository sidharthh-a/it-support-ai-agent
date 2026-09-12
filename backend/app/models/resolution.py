from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Resolution(Base):
    __tablename__ = "resolutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"), unique=True, nullable=False)
    solution_summary: Mapped[str] = mapped_column(Text, nullable=False)
    steps_taken: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    ticket: Mapped["SupportTicket"] = relationship("SupportTicket", back_populates="resolution")
    resolved_by: Mapped["User"] = relationship("User", back_populates="resolutions")
