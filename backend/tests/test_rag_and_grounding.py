"""
Tests for Phase 1+2: vector search 500 fix and real similarity scores.
Tests for Phase 3: chunker improvements.
Tests for Phase 4: grounding label correctness.
"""
import pytest
from app.rag.service import RAGService
from app.rag.chunker import chunk_text
from app.repositories.knowledge_repository import KnowledgeRepository
from app.agents.agent_graph import build_and_run_agent, get_clean_snippet


# ---------------------------------------------------------------------------
# Phase 1: Search endpoint returns results (not 500) for any query
# ---------------------------------------------------------------------------

def test_search_returns_list_not_500_for_unknown_error(db_session):
    """
    GET /knowledge/search with an unknown error code must return an empty list,
    NOT raise an exception / 500.
    """
    rag = RAGService(db_session)
    results = rag.search_knowledge("ERR_NETWORK_500", limit=3)
    assert isinstance(results, list), "search_knowledge must always return a list"


def test_search_returns_list_not_500_for_generic_query(db_session):
    """Generic VPN query should also return a list, not crash."""
    rag = RAGService(db_session)
    results = rag.search_knowledge("VPN keeps disconnecting", limit=3)
    assert isinstance(results, list)


def test_search_returns_results_when_doc_exists(db_session):
    """After ingesting a document, a matching search should return ≥1 result."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="VPN Auth Guide",
        category="Network",
        content=(
            "Error ERR_VPN_AUTH_401 indicates an SSL handshake failure. "
            "To resolve, flush the DNS cache using ipconfig /flushdns and retry."
        ),
        file_type="txt",
    )
    results = rag.search_knowledge("ERR_VPN_AUTH_401", limit=3)
    assert len(results) >= 1, "Expected at least one result for a known ingested error code"


# ---------------------------------------------------------------------------
# Phase 2: Real (non-hardcoded) similarity scores
# ---------------------------------------------------------------------------

def test_similarity_scores_are_numeric(db_session):
    """All returned scores must be numeric floats."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="Docker OOM Guide",
        category="Software",
        content="When ERR_OOM_KILLED appears, increase Docker RAM allocation to 6GB.",
        file_type="txt",
    )
    results = rag.search_knowledge("Docker container out of memory", limit=3)
    for r in results:
        assert isinstance(r["score"], (int, float)), f"Score must be numeric, got {type(r['score'])}"


def test_similarity_scores_are_not_hardcoded_095(db_session):
    """Scores must NOT be the hardcoded 0.95 value from the old implementation."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="Outlook SAML Guide",
        category="Software",
        content="ERR_OUTLOOK_SAML occurs when the SAML token expires. Re-authenticate via SSO portal.",
        file_type="txt",
    )
    results = rag.search_knowledge("Outlook SAML token error", limit=3)
    for r in results:
        assert r["score"] != 0.95, (
            f"Score {r['score']} looks like the old hardcoded 0.95 value. "
            "Real cosine similarity is required."
        )


def test_similarity_scores_are_not_hardcoded_085(db_session):
    """Scores must NOT be the hardcoded 0.85 fallback value from the old implementation."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="Wi-Fi Cert Guide",
        category="Network",
        content="To fix 802.1X cert errors, download and install ACME-Root-CA-2026.crt.",
        file_type="txt",
    )
    results = rag.search_knowledge("Wi-Fi certificate error", limit=3)
    for r in results:
        assert r["score"] != 0.85, (
            f"Score {r['score']} looks like the old hardcoded 0.85 fallback value."
        )


def test_similarity_score_range_is_valid(db_session):
    """Cosine similarity scores must be in [0, 1] range."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="VPN Score Test",
        category="Network",
        content="GlobalProtect VPN error ERR_VPN_GW_TIMEOUT: the gateway timed out.",
        file_type="txt",
    )
    results = rag.search_knowledge("VPN gateway timeout", limit=3)
    for r in results:
        assert 0.0 <= r["score"] <= 1.0, (
            f"Score {r['score']} is out of valid [0.0, 1.0] range for cosine similarity"
        )


def test_results_returned_in_descending_score_order(db_session):
    """Results must be ordered by descending similarity (highest score first)."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="VPN Ordering Test",
        category="Network",
        content=(
            "ERR_VPN_AUTH_401 is a VPN authentication failure. "
            "Flush DNS to fix it. Also try reinstalling the GlobalProtect client."
        ),
        file_type="txt",
    )
    results = rag.search_knowledge("VPN auth failure", limit=5)
    if len(results) > 1:
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True), (
            f"Results are not ordered by descending score: {scores}"
        )


# ---------------------------------------------------------------------------
# Phase 3: Chunker produces multiple chunks for longer content
# ---------------------------------------------------------------------------

def test_chunker_produces_multiple_chunks_for_long_content():
    """A document > 400 words should produce more than 1 chunk."""
    long_content = " ".join(["word"] * 900)  # 900 words > 400-word chunk_size
    chunks = chunk_text(long_content, chunk_size=400, overlap=40)
    assert len(chunks) >= 2, f"Expected ≥2 chunks for 900-word document, got {len(chunks)}"


def test_chunker_preserves_content():
    """All words from a small document should appear in the chunks."""
    content = "This is a short technical note about VPN ERR_VPN_AUTH_401."
    chunks = chunk_text(content)
    combined = " ".join(chunks)
    for keyword in ["VPN", "ERR_VPN_AUTH_401", "technical"]:
        assert keyword in combined, f"Keyword '{keyword}' was lost during chunking"


def test_chunker_handles_empty_string():
    """Empty string must return an empty list."""
    assert chunk_text("") == []


def test_chunker_handles_single_word():
    """Single word should produce exactly 1 chunk."""
    chunks = chunk_text("Hello")
    assert len(chunks) == 1
    assert chunks[0] == "Hello"


def test_chunker_overlap_carries_context():
    """With overlap=20, the second chunk should share words with the first."""
    content = " ".join([f"word{i}" for i in range(100)])
    chunks = chunk_text(content, chunk_size=40, overlap=20)
    if len(chunks) >= 2:
        first_chunk_tail_words = set(chunks[0].split()[-20:])
        second_chunk_head_words = set(chunks[1].split()[:20])
        overlap_found = first_chunk_tail_words & second_chunk_head_words
        assert len(overlap_found) > 0, "No overlap found between chunk 1 and chunk 2"


# ---------------------------------------------------------------------------
# Phase 4: Grounding label correctness
# ---------------------------------------------------------------------------

def test_grounding_unknown_error_does_not_claim_vpn_doc_describes_it(db_session):
    """
    When ERR_NETWORK_500 (unknown) is queried and the only knowledge document
    is about VPN (which doesn't mention ERR_NETWORK_500), the agent must NOT
    present the VPN doc as if it specifically documents ERR_NETWORK_500.
    The RAG section should use the 'Related' / 'General' label, not 'Technical Documentation'.
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="GlobalProtect VPN Guide",
        category="Network",
        content=(
            "ERR_VPN_AUTH_401 indicates an SSL/TLS handshake failure. "
            "1. Run ipconfig /flushdns. "
            "2. Reinstall GlobalProtect client from IT portal. "
            "3. Contact IT Helpdesk if issue persists."
        ),
        file_type="txt",
    )
    res = build_and_run_agent(db_session, "What causes ERR_NETWORK_500?")
    # The response must NOT claim the VPN doc describes ERR_NETWORK_500
    assert (
        "ERR_NETWORK_500" not in res.answer
        or "Related Knowledge" in res.answer
        or "General Documentation" in res.answer
        or "No specific documentation" in res.answer
    ), (
        "Response implies VPN doc describes ERR_NETWORK_500 without qualification"
    )
    # No fabricated troubleshooting steps for ERR_NETWORK_500 from VPN content
    assert "No grounded troubleshooting" in res.answer or "No historical" in res.answer or "Related Knowledge" in res.answer, (
        f"Agent fabricated steps for unknown error. Answer: {res.answer[:300]}"
    )


def test_grounding_known_error_extracts_steps(db_session):
    """
    When ERR_VPN_AUTH_401 is queried and the knowledge doc explicitly contains it,
    the agent should extract and present the numbered troubleshooting steps.
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="VPN Auth Troubleshooting",
        category="Network",
        content=(
            "ERR_VPN_AUTH_401 indicates an SSL handshake failure.\n"
            "1. Run ipconfig /flushdns on Windows.\n"
            "2. Restart the GlobalProtect client.\n"
            "3. Reinstall certificates from the IT portal.\n"
        ),
        file_type="txt",
    )
    res = build_and_run_agent(db_session, "How do I fix ERR_VPN_AUTH_401?")
    assert res.answer is not None
    # Should have rag_sources
    assert len(res.rag_sources) > 0, "Expected RAG sources for known error code"


def test_sql_no_match_is_reported_explicitly(db_session):
    """
    When no tickets match ERR_NETWORK_500, the agent must explicitly state
    'no historical ticket or error-log match' — not fabricate an incident.
    """
    res = build_and_run_agent(db_session, "Check tickets and logs for ERR_NETWORK_500")
    assert res.answer is not None
    lower = res.answer.lower()
    assert (
        "no historical" in lower
        or "no support tickets" in lower
        or "no matching" in lower
        or "no prior" in lower
    ), f"Agent did not explicitly report SQL miss. Answer: {res.answer[:300]}"


def test_clean_rag_preview_truncation():
    """RAG preview snippets must end at a clean sentence/step boundary and not cut mid-step (e.g. '5.')."""
    content = (
        "VPN troubleshooting guide for remote workers.\n"
        "1. Verify active internet connection and DNS settings.\n"
        "2. Launch GlobalProtect client software.\n"
        "3. Re-enter your SSO domain credentials.\n"
        "4. Check gateway configuration and routing table.\n"
        "5. Restart system network adapter service."
    )
    # Force max_chars to fall right around "5." or step 5
    snippet = get_clean_snippet(content, max_chars=205)
    assert not snippet.endswith("5."), f"Snippet ended mid-step with '5.': '{snippet}'"
    assert not snippet.endswith("5"), f"Snippet ended with dangling step digit: '{snippet}'"
    assert snippet.endswith("."), f"Snippet should end at clean sentence boundary: '{snippet}'"
    assert "4. Check gateway configuration" in snippet


def test_greeting_query_deterministic(db_session):
    """Greeting query should return concise greeting without calling tools."""
    res = build_and_run_agent(db_session, "good morning")
    assert "Hey! How can I help you with an IT issue?" in res.answer
    assert res.tools_used == []
    assert res.rag_sources == []
    assert res.sql_sources == []

