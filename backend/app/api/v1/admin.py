"""Admin panel endpoints: system health, model configuration, embedding reindex, logs."""
import platform
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import require_roles
from app.core.security import ROLE_ADMIN
from app.db.session import get_db
from app.models.knowledge import DocumentChunk, KnowledgeDocument
from app.models.user import User
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.user import UserRead
from app.schemas.user import UserAdminCreate, UserAdminUpdate
from app.repositories.user_repository import UserRepository

router = APIRouter()


@router.get("/system", response_model=Dict[str, Any])
def system_info(current_user: User = Depends(require_roles(ROLE_ADMIN)), db: Session = Depends(get_db)):
    """System health snapshot: DB, embedding model, LLM configuration, versions."""
    db_latency_ms = None
    db_ok = True
    try:
        import time
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        db_ok = False

    total_docs = db.scalar(select(func.count(KnowledgeDocument.id))) or 0
    total_chunks = db.scalar(select(func.count(DocumentChunk.id))) or 0
    embedded_chunks = db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.embedding.isnot(None))
    ) or 0

    return {
        "status": "ok" if db_ok else "degraded",
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "database": {
            "healthy": db_ok,
            "latency_ms": db_latency_ms,
        },
        "embedding": {
            "provider": settings.EMBEDDING_PROVIDER,
            "model": settings.LOCAL_EMBEDDING_MODEL if settings.EMBEDDING_PROVIDER == "local" else settings.EMBEDDING_MODEL,
            "dimension": settings.EMBEDDING_DIMENSION,
            "documents": total_docs,
            "chunks": total_chunks,
            "embedded_chunks": embedded_chunks,
            "embedding_coverage": round(embedded_chunks / total_chunks * 100, 1) if total_chunks else 0.0,
        },
        "llm": {
            "gemini_model": settings.GEMINI_MODEL,
            "gemini_configured": bool(settings.GEMINI_API_KEY),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/reindex-all")
def reindex_all_embeddings(current_user: User = Depends(require_roles(ROLE_ADMIN)), db: Session = Depends(get_db)):
    """Re-embed every knowledge document chunk with the current embedding model."""
    from app.rag.embeddings import embedding_service
    from app.repositories.knowledge_repository import _get_embedding_dim

    expected_dim = _get_embedding_dim()
    chunks = list(db.execute(select(DocumentChunk)).scalars().all())
    reindexed = 0
    skipped = 0
    for chunk in chunks:
        if not chunk.content or not chunk.content.strip():
            skipped += 1
            continue
        vector = embedding_service.embed_documents([chunk.content])[0]
        if len(vector) != expected_dim:
            skipped += 1
            continue
        chunk.embedding = vector
        reindexed += 1
    db.commit()
    return {"reindexed": reindexed, "skipped": skipped, "dimension": expected_dim}


@router.get("/users", response_model=List[UserRead])
def admin_list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    return UserRepository(db).get_all(skip=skip, limit=limit)


@router.post("/users", response_model=UserRead, status_code=201)
def admin_create_user(
    payload: UserAdminCreate,
    current_user: User = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    return repo.create(payload, password=payload.password)


@router.patch("/users/{user_id}", response_model=UserRead)
def admin_update_user(
    user_id: int,
    payload: UserAdminUpdate,
    current_user: User = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    fields = payload.model_dump(exclude_unset=True)
    if user.id == current_user.id and fields.get("is_active") is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    return repo.update(user, **fields)


@router.get("/logs")
def recent_system_logs(
    limit: int = 100,
    current_user: User = Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """Most recent system error logs (from the error_logs table, newest first)."""
    from app.models.error_log import ErrorLog
    stmt = select(ErrorLog).order_by(ErrorLog.timestamp.desc()).limit(min(limit, 500))
    logs = list(db.execute(stmt).scalars().all())
    return [
        {
            "id": l.id,
            "service_name": l.service_name,
            "error_code": l.error_code,
            "log_message": l.log_message,
            "timestamp": l.timestamp.isoformat(),
        }
        for l in logs
    ]
