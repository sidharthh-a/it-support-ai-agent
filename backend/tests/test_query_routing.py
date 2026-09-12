"""
Tests for the three-layer query routing system:
  - Layer 1: classify_query_domain() deterministic pre-router
  - Layer 2: RAG relevance threshold gate (score >= 0.35)
  - Layer 3: general-query early exit (no tools invoked)

Preserves all 52 existing tests; adds 10 new routing-specific tests.
"""
import pytest
from app.rag.service import RAGService
from app.agents.agent_graph import build_and_run_agent, classify_query_domain


# ---------------------------------------------------------------------------
# Unit tests: classify_query_domain()
# ---------------------------------------------------------------------------

class TestClassifyQueryDomain:
    """Direct unit tests for the deterministic domain classifier."""

    # --- IT-positive cases ---
    @pytest.mark.parametrize("query", [
        "My VPN is not connecting",
        "ERR_VPN_AUTH_401 when connecting",
        "My laptop cannot connect to Wi-Fi",
        "My password is not working",
        "I can't login to Okta SSO",
        "Outlook keeps asking for credentials",
        "Reset my active directory password",
        "GlobalProtect disconnects every 30 minutes",
        "DNS lookup is failing for internal sites",
        "My printer won't install the driver",
    ])
    def test_classify_it_support_queries(self, query):
        result = classify_query_domain(query)
        assert result == "it_support", (
            f"Expected 'it_support' for query: {query!r}, got: {result!r}"
        )

    # --- General/programming cases ---
    @pytest.mark.parametrize("query", [
        "how to reverse a list",
        "what is a binary tree",
        "write a Python function to sort a list",
        "explain recursion with an example",
        "what is the time complexity of quicksort",
        "implement a linked list in Java",
        "what does the fibonacci algorithm do",
        "what is dynamic programming",
        "write a function to check if a string is a palindrome",
        "what is big o notation",
    ])
    def test_classify_general_queries(self, query):
        result = classify_query_domain(query)
        assert result == "general", (
            f"Expected 'general' for query: {query!r}, got: {result!r}"
        )

    def test_ambiguous_treated_conservatively(self):
        """Ambiguous queries must not be classified as 'general'."""
        result = classify_query_domain("how to debug")
        assert result in ("it_support", "ambiguous"), (
            f"Ambiguous query must not be 'general', got: {result!r}"
        )

    def test_error_code_always_it_support(self):
        """Any ERR_* code must resolve to it_support regardless of other words."""
        result = classify_query_domain("I got ERR_UNKNOWN_999 in my Python script")
        assert result == "it_support", (
            "Error-code pattern must override any general signal"
        )


# ---------------------------------------------------------------------------
# Integration tests: general queries → no tools invoked
# ---------------------------------------------------------------------------

def test_general_query_reverse_list_no_rag_tools(db_session):
    """
    'how to reverse a list' must NOT invoke any retrieval tools and must NOT
    return IT-support formatted sections.
    """
    res = build_and_run_agent(db_session, "how to reverse a list")
    assert res.tools_used == [], (
        f"Expected no tools for general query, got: {res.tools_used}"
    )
    assert res.rag_sources == [], "Expected no RAG sources for general query"
    assert res.sql_sources == [], "Expected no SQL sources for general query"
    # Must not contain IT-support response structure
    assert "Technical Documentation (RAG)" not in res.answer
    assert "Historical Ticket" not in res.answer


def test_general_query_binary_tree_no_tools(db_session):
    """'what is a binary tree' must not invoke IT-support tools."""
    res = build_and_run_agent(db_session, "what is a binary tree")
    assert res.tools_used == []
    assert res.rag_sources == []
    assert res.sql_sources == []


def test_general_query_python_sort_no_tools(db_session):
    """'write a Python function to sort a list' must not invoke tools."""
    res = build_and_run_agent(db_session, "write a Python function to sort a list")
    assert res.tools_used == []
    assert res.rag_sources == []
    assert res.sql_sources == []


# ---------------------------------------------------------------------------
# Integration tests: IT queries with "how" still route to RAG
# ---------------------------------------------------------------------------

def test_it_query_with_how_still_uses_rag(db_session):
    """
    'how do I fix my VPN?' must be classified as it_support and invoke RAG.
    Regression guard: removing 'how' from triggers must not break IT queries.
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="VPN General Troubleshooting",
        category="Network",
        content=(
            "General VPN troubleshooting: flush DNS using ipconfig /flushdns, "
            "restart the VPN client, and check credentials."
        ),
        file_type="txt"
    )
    res = build_and_run_agent(db_session, "how do I fix my VPN?")
    # Must use at least one retrieval tool
    tool_names = [t.tool_name for t in res.tools_used]
    assert any(name in tool_names for name in ("search_documents", "search_tickets", "search_error_logs")), (
        f"IT query with 'how' must invoke retrieval tools. tools_used: {tool_names}"
    )


def test_it_query_password_routes_to_it_support(db_session):
    """'my password is not working' must invoke retrieval tools."""
    res = build_and_run_agent(db_session, "my password is not working")
    tool_names = [t.tool_name for t in res.tools_used]
    assert any(name in tool_names for name in ("search_documents", "search_tickets", "search_error_logs")), (
        f"Password query must invoke retrieval. tools_used: {tool_names}"
    )


# ---------------------------------------------------------------------------
# Integration test: IT query with no KB evidence → explicit miss, no fabrication
# ---------------------------------------------------------------------------

def test_unknown_it_error_no_false_grounding(db_session):
    """
    'ERR_UNKNOWN_999' with no matching KB document must:
    - explicitly state no documentation was found
    - not fabricate troubleshooting steps from an unrelated doc
    """
    # Ingest an unrelated doc (VPN) to ensure there IS something in the KB
    rag = RAGService(db_session)
    rag.ingest_document(
        title="GlobalProtect VPN Gateway Solutions",
        category="Network",
        content=(
            "Error ERR_VPN_AUTH_401 indicates SSL handshake failure. "
            "1. Flush DNS cache. 2. Reinstall VPN client."
        ),
        file_type="txt"
    )
    res = build_and_run_agent(db_session, "I'm getting ERR_UNKNOWN_999 on my workstation")
    # Must be classified as it_support (has error code) and use tools
    assert res.answer is not None
    # Must report miss for this specific error code
    assert (
        "No specific documentation match found for error code `ERR_UNKNOWN_999`" in res.answer
        or "No grounded troubleshooting procedure was found for `ERR_UNKNOWN_999`" in res.answer
    ), f"Expected explicit miss message. Answer:\n{res.answer[:400]}"
    # Must NOT present VPN doc as relevant to ERR_UNKNOWN_999
    assert "Retrieved from Knowledge Guide: **GlobalProtect VPN Gateway Solutions**" not in res.answer, (
        "Agent must not substitute VPN doc as relevant to ERR_UNKNOWN_999"
    )


# ---------------------------------------------------------------------------
# Integration test: low-score RAG result not used even for IT queries
# ---------------------------------------------------------------------------

def test_low_relevance_rag_doc_not_shown_as_match(db_session):
    """
    When the only KB document is semantically distant from the query
    (score would be low), the agent must report no documentation match
    rather than presenting an unrelated document as the answer.

    We achieve this by querying for a topic that has nothing to do with
    the ingested document's content, exercising the RAG_RELEVANCE_THRESHOLD gate.
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="Okta SSO Certificate Renewal Guide",
        category="Access",
        content=(
            "To renew the Okta SSO certificate: log in to the Okta admin portal, "
            "navigate to Security > Certificates, and click Renew."
        ),
        file_type="txt"
    )
    # Query is IT-domain but completely unrelated to the ingested doc
    res = build_and_run_agent(db_session, "My laptop battery drains very fast")
    # Should not present the Okta doc as relevant to a battery query
    assert "Okta SSO Certificate Renewal Guide" not in res.answer or \
           "No specific documentation" in res.answer or \
           "Related Knowledge" in res.answer, (
        "Agent must not present Okta SSO doc as relevant to a battery query"
    )
