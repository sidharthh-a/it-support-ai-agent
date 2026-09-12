"""Tests for extended knowledge management: preview, reindex, chunk access.

All Gemini calls are mocked by the autouse fixture in conftest.py.
"""
import pytest
from app.rag.service import RAGService

DOC_CONTENT = (
    "VPN Setup Guide:\n"
    "1. Open GlobalProtect client.\n"
    "2. Enter the portal address.\n"
    "3. Connect with corporate credentials.\n"
    "4. If authentication fails, reinstall the root certificate."
)


@pytest.fixture
def admin_headers(client):
    """Login as the seeded bootstrap admin for knowledge-management actions."""
    res = client.post("/api/v1/auth/login", json={"email": "test.user@acme-corp.com", "password": "testadmin123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def ingested_doc(db_session):
    rag = RAGService(db_session)
    return rag.ingest_document(title="VPN Setup Guide", category="Network", content=DOC_CONTENT, file_type="md")


def test_document_preview_endpoint(client, ingested_doc):
    res = client.get(f"/api/v1/knowledge/{ingested_doc.id}/preview")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "VPN Setup Guide"
    assert data["chunk_count"] > 0
    assert "GlobalProtect" in data["content"]
    assert isinstance(data["truncated"], bool)


def test_document_preview_respects_max_chars(client, ingested_doc):
    res = client.get(f"/api/v1/knowledge/{ingested_doc.id}/preview", params={"max_chars": 200})
    assert res.status_code == 200
    data = res.json()
    assert len(data["content"]) <= 200


def test_document_preview_404(client):
    res = client.get("/api/v1/knowledge/999999/preview")
    assert res.status_code == 404


def test_get_single_chunk(client, ingested_doc):
    first_chunk = ingested_doc.chunks[0]
    res = client.get(f"/api/v1/knowledge/{ingested_doc.id}/chunks/{first_chunk.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["chunk_index"] == first_chunk.chunk_index
    assert data["content"] == first_chunk.content


def test_get_chunk_404(client, ingested_doc):
    res = client.get(f"/api/v1/knowledge/{ingested_doc.id}/chunks/999999")
    assert res.status_code == 404


def test_reindex_document(client, db_session, ingested_doc, admin_headers):
    # Null out embeddings, then reindex should restore them
    from app.models.knowledge import DocumentChunk
    from sqlalchemy import select
    chunks = list(db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == ingested_doc.id)).scalars())
    for c in chunks:
        c.embedding = None
    db_session.commit()

    res = client.post(f"/api/v1/knowledge/{ingested_doc.id}/reindex", headers=admin_headers)
    assert res.status_code == 200
    db_session.expire_all()
    chunks_after = list(db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == ingested_doc.id)).scalars())
    assert all(c.embedding is not None for c in chunks_after)


def test_reindex_document_404(client, admin_headers):
    res = client.post("/api/v1/knowledge/999999/reindex", headers=admin_headers)
    assert res.status_code == 404


def test_list_documents_shows_embedding_metadata(client, ingested_doc):
    res = client.get("/api/v1/knowledge/")
    assert res.status_code == 200
    docs = res.json()
    target = next(d for d in docs if d["id"] == ingested_doc.id)
    assert len(target["chunks"]) > 0
