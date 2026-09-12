from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailRead,
    ConversationRead,
    ConversationRename,
    MessageRead,
)

router = APIRouter()


def _to_read(conv) -> ConversationRead:
    msgs = list(conv.messages or [])
    preview = next((m.content[:120] for m in reversed(msgs) if m.role == "user"), None)
    return ConversationRead(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(msgs),
        preview=preview,
    )


@router.get("/", response_model=List[ConversationRead])
def list_conversations(
    search: Optional[str] = Query(None, max_length=200),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's conversations, newest first, optionally searched."""
    repo = ConversationRepository(db)
    return [_to_read(c) for c in repo.list_for_user(current_user.id, search=search, limit=limit)]


@router.post("/", response_model=ConversationRead, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = ConversationRepository(db)
    conv = repo.create(current_user.id, title=payload.title or "New conversation")
    return _to_read(conv)


@router.get("/search", response_model=List[ConversationRead])
def search_conversations(
    q: str = Query(..., min_length=1, max_length=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = ConversationRepository(db)
    return [_to_read(c) for c in repo.list_for_user(current_user.id, search=q)]


@router.get("/{conversation_id}", response_model=ConversationDetailRead)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = ConversationRepository(db).get_by_id(conversation_id, user_id=current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    detail = _to_read(conv)
    return ConversationDetailRead(
        **detail.model_dump(),
        messages=[MessageRead.from_record(m) for m in conv.messages],
    )


@router.patch("/{conversation_id}", response_model=ConversationRead)
def rename_conversation(
    conversation_id: int,
    payload: ConversationRename,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = ConversationRepository(db).rename(conversation_id, payload.title, user_id=current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _to_read(conv)


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = ConversationRepository(db).delete(conversation_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None


@router.get("/{conversation_id}/messages", response_model=List[MessageRead])
def get_conversation_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = ConversationRepository(db).get_by_id(conversation_id, user_id=current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [MessageRead.from_record(m) for m in conv.messages]
