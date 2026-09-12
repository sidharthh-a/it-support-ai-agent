from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.streaming import run_agent_stream
from app.core.deps import get_current_user, get_current_user_optional
from app.db.session import get_db
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.agents.agent_graph import build_and_run_agent

router = APIRouter()


def _ensure_conversation(
    db: Session,
    conversation_id: Optional[int],
    user: User,
    first_message: str,
) -> Optional[int]:
    """Return a conversation id the user owns, creating one when absent."""
    repo = ConversationRepository(db)
    if conversation_id is not None:
        conv = repo.get_by_id(conversation_id, user_id=user.id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv.id
    title = first_message.strip()[:80] or "New conversation"
    return repo.create(user.id, title=title).id


@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Synchronous grounded chat endpoint. Persists messages when a conversation_id is supplied."""
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        response = build_and_run_agent(
            db=db,
            user_message=payload.message.strip(),
            history=payload.conversation_history,
        )

        # Persist the exchange when the client asked for history persistence.
        if payload.conversation_id is not None and current_user is not None:
            repo = ConversationRepository(db)
            conv = repo.get_by_id(payload.conversation_id, user_id=current_user.id)
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            repo.add_message(payload.conversation_id, "user", payload.message.strip())
            repo.add_message(
                payload.conversation_id,
                "assistant",
                response.answer,
                response=response,
            )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running AI agent: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """SSE streaming grounded chat. Streams the grounded answer token-by-token.

    Metadata (citations, tool calls, ticket references) is delivered in the
    final `done` event, so citations always match the streamed text exactly.
    """
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    message = payload.message.strip()

    # Resolve/create the conversation up front (validated against the owner).
    conversation_id: Optional[int] = None
    if current_user is not None:
        conversation_id = _ensure_conversation(db, payload.conversation_id, current_user, message)

    history = payload.conversation_history or []

    async def _persist_and_stream():
        answer_parts: List[str] = []
        final_meta = {}
        async for sse_event in run_agent_stream(
            db=db,
            user_message=message,
            history=history,
            conversation_id=conversation_id,
        ):
            # Capture the streamed text + metadata so we can persist after done.
            if sse_event.startswith("event: token"):
                try:
                    import json as _json
                    data_line = sse_event.split("\ndata: ", 1)[1]
                    answer_parts.append(_json.loads(data_line).get("delta", ""))
                except Exception:
                    pass
            elif sse_event.startswith("event: done"):
                try:
                    import json as _json
                    data_line = sse_event.split("\ndata: ", 1)[1]
                    final_meta = _json.loads(data_line)
                except Exception:
                    pass
            yield sse_event

        # Persist the full exchange once streaming completed.
        if conversation_id is not None and current_user is not None:
            try:
                repo = ConversationRepository(db)
                repo.add_message(conversation_id, "user", message)
                repo.add_message(
                    conversation_id,
                    "assistant",
                    final_meta.get("answer") or "".join(answer_parts),
                    grounded=final_meta.get("grounded"),
                    confidence=final_meta.get("confidence"),
                    evidence_used=final_meta.get("evidence_used"),
                )
            except Exception as exc:
                from app.core.logging import logger
                logger.warning("Failed to persist streamed conversation: %s", type(exc).__name__)

    return StreamingResponse(
        _persist_and_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
