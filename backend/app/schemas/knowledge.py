from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict


class DocumentChunkRead(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    metadata_json: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentBase(BaseModel):
    title: str
    category: str
    file_type: str = "markdown"
    source_url: Optional[str] = None


class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    content: str  # Full raw content to chunk and store


class KnowledgeDocumentRead(KnowledgeDocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    chunks: List[DocumentChunkRead] = []

    model_config = ConfigDict(from_attributes=True)


class SearchResult(BaseModel):
    document_id: int
    chunk_id: int
    title: str
    category: str
    content: str
    score: float
