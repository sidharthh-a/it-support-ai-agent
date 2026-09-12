from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, literal_column
from app.models.knowledge import KnowledgeDocument, DocumentChunk
from app.core.config import settings
from app.core.logging import logger


# Import lazily to avoid circular import at module load time
def _get_embedding_dim() -> int:
    """Returns the actual runtime embedding dimension from the singleton service."""
    try:
        from app.rag.embeddings import embedding_service
        return embedding_service.dimension
    except Exception:
        return settings.EMBEDDING_DIMENSION


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_documents(self) -> List[KnowledgeDocument]:
        stmt = (
            select(KnowledgeDocument)
            .options(joinedload(KnowledgeDocument.chunks))
            .order_by(KnowledgeDocument.created_at.desc())
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def get_document_by_id(self, doc_id: int) -> Optional[KnowledgeDocument]:
        stmt = (
            select(KnowledgeDocument)
            .options(joinedload(KnowledgeDocument.chunks))
            .where(KnowledgeDocument.id == doc_id)
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_existing_document(self, title: str, source_url: Optional[str] = None) -> Optional[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).options(joinedload(KnowledgeDocument.chunks))
        if source_url:
            stmt = stmt.where(or_(KnowledgeDocument.source_url == source_url, KnowledgeDocument.title == title))
        else:
            stmt = stmt.where(KnowledgeDocument.title == title)
        return self.db.execute(stmt).unique().scalars().first()

    def create_document_with_chunks(
        self,
        title: str,
        category: str,
        file_type: str = "markdown",
        source_url: Optional[str] = None,
        chunks_data: List[Tuple[str, List[float]]] = None
    ) -> KnowledgeDocument:
        existing = self.get_existing_document(title=title, source_url=source_url)
        if existing:
            return existing

        doc = KnowledgeDocument(
            title=title,
            category=category,
            file_type=file_type,
            source_url=source_url
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        if chunks_data:
            expected_dim = _get_embedding_dim()
            for idx, (content, vector_emb) in enumerate(chunks_data):
                # Accept embeddings of the configured dimension; reject mismatched ones
                valid_emb = vector_emb if (vector_emb and len(vector_emb) == expected_dim) else None
                chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=idx,
                    content=content,
                    metadata_json={"title": title, "category": category},
                    embedding=valid_emb
                )
                self.db.add(chunk)
            self.db.commit()

        return self.get_document_by_id(doc.id)

    def delete_document(self, doc_id: int) -> bool:
        doc = self.db.get(KnowledgeDocument, doc_id)
        if not doc:
            return False
        self.db.delete(doc)
        self.db.commit()
        return True

    def vector_search_chunks(
        self,
        query_embedding: Optional[List[float]],
        query_text: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge chunks using pgvector cosine similarity (primary path) with
        a keyword text-search fallback.

        Score semantics:
          - Vector results: score = 1.0 - cosine_distance  (range [0, 1], higher = more similar)
          - Text fallback results: score = 0.0  (clearly distinguishable from vector scores)
        """
        results = []

        # ------------------------------------------------------------------
        # Primary path: pgvector cosine-distance search (PostgreSQL only)
        # ------------------------------------------------------------------
        bind = self.db.get_bind()
        is_postgres = bind is not None and bind.dialect.name == "postgresql"

        if (
            is_postgres
            and query_embedding
            and len(query_embedding) == _get_embedding_dim()
        ):
            try:
                # Project the cosine distance as a named column so we can read it back.
                # Filter out chunks with NULL embeddings to avoid operator errors.
                distance_col = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
                stmt = (
                    select(DocumentChunk, KnowledgeDocument, distance_col)
                    .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
                    .where(DocumentChunk.embedding.isnot(None))
                    .order_by(distance_col)
                    .limit(limit)
                )
                rows = self.db.execute(stmt).all()
                for chunk, doc, distance in rows:
                    # cosine_similarity = 1.0 - cosine_distance
                    score = round(1.0 - float(distance), 4) if distance is not None else 0.0
                    results.append({
                        "document_id": doc.id,
                        "chunk_id": chunk.id,
                        "title": doc.title,
                        "category": doc.category,
                        "snippet": chunk.content[:200] if chunk.content else "",
                        "content": chunk.content,
                        "score": score,
                        "search_type": "vector",
                    })
                if results:
                    return results
            except Exception as e:
                # Log visibly so the failure is observable in development and production logs.
                # Roll back the session so subsequent queries on the same session can execute
                # on a clean transaction (avoids cascading InternalError → HTTP 500).
                logger.error(
                    f"[KnowledgeRepository] Vector search failed — falling back to text search. "
                    f"Error: {type(e).__name__}: {e}"
                )
                try:
                    self.db.rollback()
                except Exception as rb_err:
                    logger.warning(f"[KnowledgeRepository] Session rollback failed: {rb_err}")

        # ------------------------------------------------------------------
        # Fallback: keyword text search
        # Scores are set to 0.0 to clearly distinguish them from vector results.
        # ------------------------------------------------------------------
        import re
        tokens = set()

        # Extract standard IT error codes if present
        from app.tools.agent_tools import extract_error_code
        err_code = extract_error_code(query_text)
        if err_code:
            tokens.add(err_code)

        # Sanitize query words (strip trailing/leading punctuation)
        raw_words = query_text.split()
        for w in raw_words:
            clean_w = re.sub(r"[^\w-]", "", w)
            if len(clean_w) >= 2:
                tokens.add(clean_w)

        filters = []
        for token in tokens:
            pattern = f"%{token}%"
            filters.append(
                or_(
                    DocumentChunk.content.ilike(pattern),
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.category.ilike(pattern)
                )
            )

        if not filters:
            return results

        stmt = (
            select(DocumentChunk, KnowledgeDocument)
            .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
            .where(or_(*filters))
            .limit(limit)
        )

        try:
            rows = self.db.execute(stmt).all()
            for chunk, doc in rows:
                results.append({
                    "document_id": doc.id,
                    "chunk_id": chunk.id,
                    "title": doc.title,
                    "category": doc.category,
                    "snippet": chunk.content[:200] if chunk.content else "",
                    "content": chunk.content,
                    "score": 0.0,
                    "search_type": "text",
                })
        except Exception as e:
            logger.error(
                f"[KnowledgeRepository] Text-search fallback also failed: {type(e).__name__}: {e}"
            )
            # Return empty list rather than crashing; caller handles empty results gracefully.

        return results

