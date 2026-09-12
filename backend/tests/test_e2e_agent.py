import os
import json
import pytest
from app.rag.service import RAGService
from app.repositories.ticket_repository import TicketRepository
from app.agents.agent_graph import build_and_run_agent
from app.tools.agent_tools import create_agent_tools
from app.schemas.ticket import TicketCreate


def test_01_document_ingestion(db_session):
    """Test 1: Ingestion of TXT and PDF documents into RAG vector repository."""
    rag = RAGService(db_session)
    
    # Ingest TXT
    doc_txt = rag.ingest_document(
        title="GlobalProtect VPN Gateway Solutions",
        category="Network",
        content="Error ERR_VPN_AUTH_401 indicates SSL handshake failure. Flush DNS cache using ipconfig /flushdns.",
        file_type="txt"
    )
    assert doc_txt.id is not None
    assert len(doc_txt.chunks) > 0

    # Ingest PDF bytes
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 120 >>\nstream\nBT /F1 12 Tf 50 750 Td (Wi-Fi 802.1X Certificate Fix: Download ACME-Root-CA-2026.crt) Tj ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000113 00000 n \n0000000236 00000 n \n0000000407 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n478\n%%EOF\n"
    )
    doc_pdf = rag.ingest_file_bytes(
        title="Wi-Fi Certificate Fix PDF Guide",
        category="Network",
        file_bytes=pdf_bytes,
        filename="wifi_guide.pdf"
    )
    assert doc_pdf.id is not None
    assert doc_pdf.file_type == "pdf"


def test_02_vector_search(db_session):
    """Test 2: Semantic vector similarity search over chunked knowledge documents."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="Docker Desktop OOM Memory Guide",
        category="Software",
        content="When container crashes with ERR_OOM_KILLED, navigate to Docker Desktop Settings -> Resources and increase RAM to 6GB."
    )
    
    results = rag.search_knowledge("Docker container memory crash", limit=3)
    assert len(results) > 0
    assert any("ERR_OOM_KILLED" in r["content"] for r in results)


def test_03_sql_ticket_search(db_session):
    """Test 3: SQL structured ticket search via TicketRepository."""
    repo = TicketRepository(db_session)
    repo.create_ticket(TicketCreate(
        title="Outlook SAML Token Expiration",
        description="User prompted repeatedly for credentials with error ERR_OUTLOOK_SAML.",
        priority="high",
        category="software",
        user_id=1
    ))
    
    tickets = repo.search_tickets(query="Outlook")
    assert len(tickets) >= 1
    assert tickets[0].category == "software"


def test_04_rag_only_query(db_session):
    """Test 4: Agent handling of RAG-only technical documentation query."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="VPN Setup Guide",
        category="Network",
        content="To solve ERR_VPN_AUTH_401 timeout, clear DNS cache with ipconfig /flushdns."
    )
    
    res = build_and_run_agent(db_session, "How do I fix ERR_VPN_AUTH_401 in the VPN guide?")
    assert res.answer is not None
    assert "Documentation" in res.answer or len(res.rag_sources) > 0


def test_05_sql_only_query(db_session):
    """Test 5: Agent handling of SQL-only query querying historical tickets."""
    repo = TicketRepository(db_session)
    repo.create_ticket(TicketCreate(
        title="Wi-Fi WPA3 Disconnection",
        description="Wi-Fi disconnected with ERR_8021X_CERT_EXPIRED.",
        priority="critical",
        category="network",
        user_id=1
    ))
    
    res = build_and_run_agent(db_session, "Search previous tickets for Wi-Fi disconnection history")
    assert res.answer is not None
    assert len(res.sql_sources) > 0


def test_06_combined_rag_and_sql_query(db_session):
    """Test 6: Dual retrieval agent combining RAG docs + SQL tickets into grounded response."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="VPN Troubleshooting Guide",
        category="Network",
        content="For GlobalProtect timeout, clear local DNS cache and refresh connection."
    )
    repo = TicketRepository(db_session)
    repo.create_ticket(TicketCreate(
        title="GlobalProtect VPN Disconnecting",
        description="Gateway timeout when connecting to vpn-east.acme-corp.com.",
        priority="high",
        category="network",
        user_id=1
    ))

    res = build_and_run_agent(db_session, "My VPN keeps disconnecting. Has this happened before and how do I fix it?")
    assert res.answer is not None
    assert len(res.tools_used) >= 2
    assert "Technical Documentation" in res.answer or "RAG" in res.answer


def test_07_ticket_creation(db_session):
    """Test 7: Explicit ticket creation tool execution."""
    res = build_and_run_agent(db_session, "Please create ticket: Blue screen kernel panic error on workstation.")
    assert res.ticket_created is not None
    assert res.ticket_created["ticket_number"].startswith("TICK-")


def test_08_agent_tool_selection(db_session):
    """Test 8: Agent tool selection registry."""
    tools = create_agent_tools(db_session)
    tool_names = [t.name for t in tools]
    expected_tools = ["search_documents", "search_tickets", "get_ticket_history", "search_error_logs", "create_ticket", "update_ticket"]
    for et in expected_tools:
        assert et in tool_names


def test_09_escalation_workflow(db_session):
    """Test 9: Critical urgency escalation workflow."""
    res = build_and_run_agent(db_session, "CRITICAL URGENT OUTAGE: Corporate SSO gateway completely down across all departments!")
    assert res.ticket_created is not None
    assert res.ticket_created["priority"] == "critical"
