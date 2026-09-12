from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict

from app.models.conversation import ChatMessageRecord


class ConversationCreate(BaseModel):
    title: Optional[str] = "New conversation"


class ConversationRename(BaseModel):
    title: str


class ConversationRead(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    preview: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MessageRead(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    tools_used: Optional[List[Dict[str, Any]]] = None
    rag_sources: Optional[List[Dict[str, Any]]] = None
    sql_sources: Optional[List[Dict[str, Any]]] = None
    ticket_created: Optional[Dict[str, Any]] = None
    ticket_updated: Optional[Dict[str, Any]] = None
    grounded: Optional[bool] = None
    confidence: Optional[float] = None
    evidence_used: Optional[List[str]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_record(cls, rec: ChatMessageRecord) -> "MessageRead":
        return cls(
            id=rec.id,
            conversation_id=rec.conversation_id,
            role=rec.role,
            content=rec.content,
            tools_used=rec.tools_used,
            rag_sources=rec.rag_sources,
            sql_sources=rec.sql_sources,
            ticket_created=rec.ticket_created,
            ticket_updated=rec.ticket_updated,
            grounded=rec.grounded,
            confidence=rec.confidence,
            evidence_used=rec.evidence_used,
            created_at=rec.created_at,
        )


class ConversationDetailRead(ConversationRead):
    messages: List[MessageRead] = []


class ChatHistoryItem(BaseModel):
    role: str
    content: str
