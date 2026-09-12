from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.compiler import compiles
from pgvector.sqlalchemy import Vector
from app.db.base import Base


@compiles(Vector, "sqlite")
def compile_vector_sqlite(element, compiler, **kw):
    return "TEXT"


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), default="markdown", nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    chunks: Mapped[List["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # 384-dimensional vector for local SentenceTransformers (all-MiniLM-L6-v2)
    # Use EMBEDDING_DIMENSION env var (default 384) to control this at migration time
    embedding = mapped_column(Vector(384), nullable=True)

    # Relationships
    document: Mapped["KnowledgeDocument"] = relationship("KnowledgeDocument", back_populates="chunks")
