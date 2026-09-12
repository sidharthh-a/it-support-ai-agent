from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_db

router = APIRouter()


def _check_db(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/live")
def liveness():
    """Liveness probe: process is up. Never touches the database."""
    return {"status": "ok", "service": settings.PROJECT_NAME}


@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """Readiness probe: process up AND database reachable."""
    db_ok = _check_db(db)
    return {
        "status": "ready" if db_ok else "degraded",
        "database": "reachable" if db_ok else "unreachable",
    }


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Detailed health: database, embedding model, and LLM configuration."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    embedding_info = {"provider": settings.EMBEDDING_PROVIDER, "dimension": settings.EMBEDDING_DIMENSION}
    llm_info = {
        "gemini_model": settings.GEMINI_MODEL,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
    }

    overall = "ok" if db_status == "healthy" else "degraded"
    return {
        "status": overall,
        "service": "IT Support AI Agent Backend",
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
        "database": db_status,
        "embedding": embedding_info,
        "llm": llm_info,
    }
