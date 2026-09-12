from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.conversation import Conversation, ChatMessageRecord
from app.schemas.chat import ChatResponse


class ConversationRepository:
    """Repository pattern: all conversation/message persistence flows through here."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------
    def get_by_id(self, conversation_id: int, user_id: Optional[int] = None) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id)
        )
        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def list_for_user(
        self,
        user_id: int,
        search: Optional[str] = None,
        limit: int = 100,
    ) -> List[Conversation]:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.user_id == user_id)
        )
        if search:
            pattern = f"%{search}%"
            # Match on title OR any contained message content
            stmt = stmt.where(
                or_(
                    Conversation.title.ilike(pattern),
                    Conversation.messages.any(ChatMessageRecord.content.ilike(pattern)),
                )
            )
        stmt = stmt.order_by(Conversation.updated_at.desc()).limit(limit)
        return list(self.db.execute(stmt).unique().scalars().all())

    def create(self, user_id: int, title: str = "New conversation") -> Conversation:
        conv = Conversation(user_id=user_id, title=title[:255])
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def rename(self, conversation_id: int, title: str, user_id: Optional[int] = None) -> Optional[Conversation]:
        conv = self.get_by_id(conversation_id, user_id=user_id)
        if not conv:
            return None
        conv.title = title.strip()[:255] or conv.title
        conv.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def touch(self, conversation_id: int) -> None:
        conv = self.db.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            self.db.commit()

    def delete(self, conversation_id: int, user_id: Optional[int] = None) -> bool:
        conv = self.get_by_id(conversation_id, user_id=user_id)
        if not conv:
            return False
        self.db.delete(conv)
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------
    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        response: Optional[ChatResponse] = None,
        grounded: Optional[bool] = None,
        confidence: Optional[float] = None,
        evidence_used: Optional[List[str]] = None,
    ) -> ChatMessageRecord:
        msg = ChatMessageRecord(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        if response is not None:
            msg.tools_used = [t.model_dump() for t in response.tools_used]
            msg.rag_sources = response.rag_sources
            msg.sql_sources = response.sql_sources
            msg.ticket_created = response.ticket_created
            msg.ticket_updated = response.ticket_updated
        msg.grounded = grounded
        msg.confidence = confidence
        msg.evidence_used = evidence_used
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        self.touch(conversation_id)
        return msg

    def get_messages(self, conversation_id: int) -> List[ChatMessageRecord]:
        stmt = (
            select(ChatMessageRecord)
            .where(ChatMessageRecord.conversation_id == conversation_id)
            .order_by(ChatMessageRecord.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())
