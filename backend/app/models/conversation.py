"""Conversation & Message ORM models for persistent chat history.

A Conversation groups messages; each assistant message preserves the full
grounded-agent metadata (tool calls, RAG/SQL citations, ticket references).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="New conversation", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False, index=True
    )

    user: Mapped["User"] = relationship("User")
    messages: Mapped[List["ChatMessageRecord"]] = relationship(
        "ChatMessageRecord", back_populates="conversation", cascade="all, delete-orphan",
        order_by="ChatMessageRecord.created_at",
    )


class ChatMessageRecord(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Grounded-agent metadata (assistant messages)
    tools_used: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    rag_sources: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    sql_sources: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    ticket_created: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ticket_updated: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    grounded: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_used: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
