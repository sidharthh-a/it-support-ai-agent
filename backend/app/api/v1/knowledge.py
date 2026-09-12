import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.deps import get_current_user, require_roles
from app.core.security import ROLE_ADMIN, ROLE_SUPPORT, normalize_role
from app.rag.service import RAGService
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import KnowledgeDocumentCreate, KnowledgeDocumentRead, SearchResult
from app.core.logging import logger

router = APIRouter()

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".json"}


def _user_can_manage(user) -> bool:
    """Support engineers and admins manage the knowledge base."""
    return normalize_role(user.role) in (ROLE_SUPPORT, ROLE_ADMIN)


@router.get("/", response_model=List[KnowledgeDocumentRead])
def list_documents(db: Session = Depends(get_db)):
    repo = KnowledgeRepository(db)
    return repo.get_all_documents()


@router.get("/search", response_model=List[SearchResult])
def search_knowledge(
    q: str = Query(..., description="Query string for vector semantic search"),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    try:
        rag = RAGService(db)
        return rag.search_knowledge(query=q, limit=limit)
    except Exception as e:
        logger.error(f"[knowledge/search] Unhandled exception for query={q!r}: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge search failed: {type(e).__name__}: {e}"
        )


@router.get("/{doc_id}/preview")
def preview_document(
    doc_id: int,
    max_chars: int = Query(4000, ge=200, le=20000),
    db: Session = Depends(get_db),
):
    """Full-text preview of a knowledge document assembled from its chunks."""
    repo = KnowledgeRepository(db)
    doc = repo.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    ordered = sorted(doc.chunks, key=lambda c: c.chunk_index)
    content = "\n\n".join(c.content for c in ordered)[:max_chars]
    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category,
        "file_type": doc.file_type,
        "source_url": doc.source_url,
        "created_at": doc.created_at,
        "chunk_count": len(ordered),
        "content": content,
        "truncated": sum(len(c.content) for c in ordered) > max_chars,
    }


@router.get("/{doc_id}/chunks/{chunk_id}")
def get_chunk(chunk_id: int, db: Session = Depends(get_db)):
    """Single chunk retrieval (used to display cited chunk context)."""
    from app.models.knowledge import DocumentChunk
    chunk = db.get(DocumentChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata_json": chunk.metadata_json,
    }


@router.post("/{doc_id}/reindex", response_model=KnowledgeDocumentRead)
def reindex_document(
    doc_id: int,
    current_user=Depends(require_roles(ROLE_SUPPORT, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    """Re-embed all chunks of a document with the current embedding model."""
    repo = KnowledgeRepository(db)
    doc = repo.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        updated = RAGService(db).reindex_document(doc_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reindex failed: {type(e).__name__}: {e}")
    if not updated:
        raise HTTPException(status_code=404, detail="Document not found")
    return updated


@router.post("/", response_model=KnowledgeDocumentRead, status_code=201)
def upload_document_json(doc_in: KnowledgeDocumentCreate, db: Session = Depends(get_db)):
    rag = RAGService(db)
    doc = rag.ingest_document(
        title=doc_in.title,
        category=doc_in.category,
        content=doc_in.content,
        file_type=doc_in.file_type,
        source_url=doc_in.source_url
    )
    return doc


@router.post("/upload", response_model=KnowledgeDocumentRead, status_code=201)
async def upload_document_file(
    title: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    source_url: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    filename = file.filename or "uploaded_doc.txt"
    ext = os.path.splitext(filename)[1].lower()
    if not ext or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed limit of 10 MB."
        )

    if ext == ".pdf" and not file_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail="File content does not match a valid PDF document."
        )

    rag = RAGService(db)
    try:
        doc = rag.ingest_file_bytes(
            title=title,
            category=category,
            file_bytes=file_bytes,
            filename=filename,
            source_url=source_url
        )
        return doc
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process document upload: {str(e)}")


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: int,
    current_user=Depends(require_roles(ROLE_SUPPORT, ROLE_ADMIN)),
    db: Session = Depends(get_db)
):
    rag = RAGService(db)
    deleted = rag.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return None
