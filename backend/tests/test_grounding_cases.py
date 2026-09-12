import pytest
from app.rag.service import RAGService
from app.agents.agent_graph import build_and_run_agent


def test_case_a_known_error_with_history_and_rag(db_session):
    """
    Test Case A:
    Query: "My VPN keeps disconnecting with ERR_VPN_AUTH_401. Has this happened before and how do I fix it?"
    Expected:
    - relevant VPN RAG document
    - matching historical tickets/logs
    - grounded troubleshooting
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="GlobalProtect VPN Gateway Solutions",
        category="Network",
        content=(
            "Error ERR_VPN_AUTH_401 indicates SSL handshake failure.\n"
            "1. Flush DNS cache using ipconfig /flushdns.\n"
            "2. Download and reinstall ACME-Root-CA-2026.crt certificate.\n"
            "3. Restart the GlobalProtect VPN client."
        ),
        file_type="txt"
    )

    res = build_and_run_agent(
        db_session,
        "My VPN keeps disconnecting with ERR_VPN_AUTH_401. Has this happened before and how do I fix it?"
    )

    # 1. Relevant VPN RAG document
    assert len(res.rag_sources) > 0
    assert "GlobalProtect VPN" in res.answer or "ERR_VPN_AUTH_401" in res.answer

    # 2. Grounded troubleshooting steps
    assert "ipconfig /flushdns" in res.answer
    assert "ACME-Root-CA-2026.crt" in res.answer

    # 3. SQL context present
    assert "Historical Ticket & Log Context" in res.answer


def test_case_b_unknown_error_no_false_grounding(db_session):
    """
    Test Case B:
    Query: "I am getting ERR_NETWORK_500 when connecting to the VPN. How can I fix it?"
    Expected:
    - no false ERR_VPN_AUTH_401 troubleshooting
    - no unrelated document presented as the answer
    - explicit lack of grounded procedure/history
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="GlobalProtect VPN Gateway Solutions",
        category="Network",
        content=(
            "Error ERR_VPN_AUTH_401 indicates SSL handshake failure.\n"
            "1. Flush DNS cache using ipconfig /flushdns.\n"
            "2. Download and reinstall ACME-Root-CA-2026.crt certificate."
        ),
        file_type="txt"
    )

    res = build_and_run_agent(
        db_session,
        "I am getting ERR_NETWORK_500 when connecting to the VPN. How can I fix it?"
    )

    # Must NOT present ERR_VPN_AUTH_401 document as the matching technical documentation
    assert "Retrieved from Knowledge Guide: **GlobalProtect VPN Gateway Solutions**" not in res.answer

    # Must NOT contain false ERR_VPN_AUTH_401 troubleshooting
    assert "No grounded troubleshooting procedure was found for `ERR_NETWORK_500`" in res.answer

    # Explicit lack of history for ERR_NETWORK_500
    assert "No historical ticket or error-log match found for error code `ERR_NETWORK_500`" in res.answer


def test_case_c_generic_query_no_unsupported_assumptions(db_session):
    """
    Test Case C:
    Query: "My VPN is not connecting. What should I check?"
    Expected:
    - no unsupported assumption that the error is ERR_VPN_AUTH_401
    - general/related documentation only if genuinely relevant
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="GlobalProtect VPN Gateway Solutions",
        category="Network",
        content=(
            "General VPN Troubleshooting Guide:\n"
            "1. Flush DNS cache using ipconfig /flushdns.\n"
            "2. Verify Wi-Fi 802.1X network connection.\n"
            "3. Reinstall VPN client if SSL errors occur."
        ),
        file_type="txt"
    )

    res = build_and_run_agent(
        db_session,
        "My VPN is not connecting. What should I check?"
    )

    # Must NOT assume user has ERR_VPN_AUTH_401 when they didn't specify it
    assert "ERR_VPN_AUTH_401 indicates" not in res.answer

    # Document should be labeled appropriately or provide general steps
    assert "ipconfig /flushdns" in res.answer or "Grounded Troubleshooting" in res.answer


def test_case_d_full_certificate_filename_not_truncated(db_session):
    """
    Test Case D:
    Verify the full certificate filename (ACME-Root-CA-2026.crt) appears in the final troubleshooting steps.
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="Wi-Fi 802.1X Certificate Fix",
        category="Network",
        content=(
            "To resolve 802.1X certificate authentication errors:\n"
            "1. Download and reinstall ACME-Root-CA-2026.crt certificate.\n"
            "2. Restart the network adapter."
        ),
        file_type="txt"
    )

    res = build_and_run_agent(
        db_session,
        "How do I fix the Wi-Fi 802.1X certificate error?"
    )

    # Full certificate filename must appear completely in the answer
    assert "ACME-Root-CA-2026.crt" in res.answer, f"Certificate filename was truncated. Full answer:\n{res.answer}"
    assert "ACME-Root-CA-" not in res.answer.replace("ACME-Root-CA-2026.crt", "")

def test_case_e_no_rag_match_returns_no_grounded_procedure_message(db_session):
    """
    Test Case E:
    Query: "my screen won't turn on" (IT query with no relevant KB match)
    Expected:
    - Response does NOT contain VPN-specific troubleshooting instructions
    - Response contains the explicit no-grounded-procedure message
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="GlobalProtect VPN Gateway Solutions",
        category="Network",
        content=(
            "Error ERR_VPN_AUTH_401 indicates SSL handshake failure.\n"
            "1. Flush DNS cache using ipconfig /flushdns.\n"
            "2. Download and reinstall ACME-Root-CA-2026.crt certificate."
        ),
        file_type="txt"
    )

    res = build_and_run_agent(
        db_session,
        "my screen won't turn on"
    )

    # 1. Must NOT contain fabricated VPN troubleshooting steps
    assert "Check VPN client connection settings" not in res.answer
    assert "Verify active internet connectivity" not in res.answer
    assert "Collect client connection logs" not in res.answer

    # 2. Must contain the exact no-grounded-procedure message
    assert "No grounded troubleshooting procedure was found in the knowledge base. Please contact your IT administrator or submit an IT support ticket." in res.answer


def test_case_f_empty_knowledge_base_no_unsupported_steps(db_session):
    """
    Test Case F:
    Empty KB with an IT query should return the no-grounded-procedure message
    and zero fabricated VPN instructions.
    """
    res = build_and_run_agent(
        db_session,
        "How do I fix my monitor display flickering?"
    )

    assert "Check VPN client connection settings" not in res.answer
    assert "Verify active internet connectivity" not in res.answer
    assert "No grounded troubleshooting procedure was found in the knowledge base. Please contact your IT administrator or submit an IT support ticket." in res.answer

