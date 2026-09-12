import os
import pytest
from app.rag.service import RAGService
from app.repositories.knowledge_repository import KnowledgeRepository
from app.models.knowledge import KnowledgeDocument, DocumentChunk

def test_idempotent_pdf_ingestion(db_session):
    """Test that ingesting the exact same PDF or document twice does NOT duplicate records."""
    rag = RAGService(db_session)
    repo = KnowledgeRepository(db_session)

    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 120 >>\nstream\nBT /F1 12 Tf 50 750 Td (Idempotency Test PDF content for VPN setup) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000056 00000 n \n0000000113 00000 n \n0000000236 00000 n \n0000000407 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n478\n%%EOF\n"
    )
    title = "Idempotent Test PDF Guide"
    category = "Network"
    filename = "idempotent_test.pdf"
    source_url = "https://wiki.acme-corp.internal/test/idempotent-pdf"

    # Count initial docs and chunks
    initial_docs_count = len(repo.get_all_documents())

    # Ingestion 1
    doc_1 = rag.ingest_file_bytes(
        title=title,
        category=category,
        file_bytes=pdf_bytes,
        filename=filename,
        source_url=source_url
    )
    assert doc_1.id is not None
    chunks_count_1 = len(doc_1.chunks)
    assert chunks_count_1 > 0
    
    docs_after_first = repo.get_all_documents()
    assert len(docs_after_first) == initial_docs_count + 1

    # Ingestion 2 (exact same file)
    doc_2 = rag.ingest_file_bytes(
        title=title,
        category=category,
        file_bytes=pdf_bytes,
        filename=filename,
        source_url=source_url
    )
    
    docs_after_second = repo.get_all_documents()

    # Verify ID is identical, doc count hasn't increased, chunk count hasn't increased
    assert doc_2.id == doc_1.id
    assert len(docs_after_second) == len(docs_after_first)
    assert len(doc_2.chunks) == chunks_count_1
