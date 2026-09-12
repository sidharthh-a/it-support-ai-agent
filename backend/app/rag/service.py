from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.rag.chunker import chunk_text, extract_text_from_file_bytes
from app.rag.embeddings import embedding_service
from app.repositories.knowledge_repository import KnowledgeRepository


class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.knowledge_repo = KnowledgeRepository(db)

    def ingest_document(
        self,
        title: str,
        category: str,
        content: str,
        file_type: str = "markdown",
        source_url: Optional[str] = None
    ) -> Any:
        existing = self.knowledge_repo.get_existing_document(title=title, source_url=source_url)
        if existing:
            return existing

        chunks = chunk_text(content)
        embeddings = embedding_service.embed_documents(chunks)
        
        chunks_data = list(zip(chunks, embeddings))
        return self.knowledge_repo.create_document_with_chunks(
            title=title,
            category=category,
            file_type=file_type,
            source_url=source_url,
            chunks_data=chunks_data
        )

    def ingest_file_bytes(
        self,
        title: str,
        category: str,
        file_bytes: bytes,
        filename: str,
        source_url: Optional[str] = None
    ) -> Any:
        content = extract_text_from_file_bytes(file_bytes, filename)
        file_type = filename.split(".")[-1].lower() if "." in filename else "txt"
        return self.ingest_document(
            title=title,
            category=category,
            content=content,
            file_type=file_type,
            source_url=source_url
        )

    def delete_document(self, doc_id: int) -> bool:
        return self.knowledge_repo.delete_document(doc_id)

    def reindex_document(self, doc_id: int):
        """Re-embed every chunk of a document with the current embedding model."""
        from app.repositories.knowledge_repository import _get_embedding_dim
        doc = self.knowledge_repo.get_document_by_id(doc_id)
        if not doc:
            return None
        expected_dim = _get_embedding_dim()
        ordered = sorted(doc.chunks, key=lambda c: c.chunk_index)
        contents = [c.content for c in ordered if c.content and c.content.strip()]
        if contents:
            vectors = embedding_service.embed_documents(contents)
            for chunk, vector in zip([c for c in ordered if c.content and c.content.strip()], vectors):
                chunk.embedding = vector if len(vector) == expected_dim else None
            self.db.commit()
        return self.knowledge_repo.get_document_by_id(doc_id)

    def search_knowledge(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query_vector = embedding_service.embed_query(query)
        return self.knowledge_repo.vector_search_chunks(
            query_embedding=query_vector,
            query_text=query,
            limit=limit
        )
