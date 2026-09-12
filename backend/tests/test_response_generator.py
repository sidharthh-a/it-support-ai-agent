"""
Comprehensive Tests for Grounded Gemini Response Generator (Phase 3 Step 3.1).

All Gemini calls are strictly mocked; zero live Gemini API calls are made.
Verifies grounded RAG, ticket, and error responses, unknown error code handling,
no-evidence behavior, failure/malformed/invalid fallbacks, and isolation of
CASUAL, GENERAL, and AMBIGUOUS queries.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError

from app.agents.response_generator import (
    generate_grounded_response,
    build_deterministic_fallback,
    has_usable_evidence,
    get_gemini_client,
    EvidenceBundle,
    GroundedResponse,
    NO_GROUNDED_PROCEDURE_MSG,
)
from app.agents.agent_graph import build_and_run_agent
from app.rag.service import RAGService


def _create_mock_gemini_client(response_dict_or_text):
    """Helper to produce a mock Google GenAI client returning response text."""
    client = MagicMock()
    mock_resp = MagicMock()
    if isinstance(response_dict_or_text, dict):
        mock_resp.text = json.dumps(response_dict_or_text)
    else:
        mock_resp.text = str(response_dict_or_text)
    client.models.generate_content.return_value = mock_resp
    return client


# ---------------------------------------------------------------------------
# Test A: Grounded RAG response
# ---------------------------------------------------------------------------

def test_a_grounded_rag_response():
    """Provide a known RAG document, mock Gemini response, verify it is returned."""
    evidence = EvidenceBundle(
        query="How do I fix the GlobalProtect SSL handshake failure?",
        rag_docs=[{
            "title": "GlobalProtect VPN Gateway Solutions",
            "category": "Network",
            "content": (
                "Error ERR_VPN_AUTH_401 indicates SSL handshake failure.\n"
                "1. Flush DNS cache using ipconfig /flushdns.\n"
                "2. Download and reinstall ACME-Root-CA-2026.crt certificate."
            ),
        }],
    )
    expected_answer = (
        "Summary: The SSL handshake failure is addressed in the GlobalProtect documentation.\n"
        "Recommended steps:\n"
        "1. Flush DNS cache using ipconfig /flushdns.\n"
        "2. Download and reinstall ACME-Root-CA-2026.crt certificate.\n"
        "Source: GlobalProtect VPN Gateway Solutions"
    )
    mock_client = _create_mock_gemini_client({
        "answer": expected_answer,
        "grounded": True,
        "confidence": 0.95,
        "evidence_used": ["GlobalProtect VPN Gateway Solutions"],
    })

    result = generate_grounded_response(
        query="How do I fix the GlobalProtect SSL handshake failure?",
        evidence=evidence,
        client=mock_client,
    )

    assert result.grounded is True
    assert result.confidence == 0.95
    assert result.answer == expected_answer
    assert "GlobalProtect VPN Gateway Solutions" in result.evidence_used
    mock_client.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# Test B: Grounded ticket response
# ---------------------------------------------------------------------------

def test_b_grounded_ticket_response():
    """Provide historical ticket evidence, verify Gemini receives that evidence."""
    ticket_text = (
        "Ticket #101: GlobalProtect connection failure - Resolved\n"
        "Resolution: User reinstalled ACME-Root-CA-2026.crt certificate."
    )
    evidence = EvidenceBundle(
        query="Has this GlobalProtect issue happened before?",
        tickets=[ticket_text],
        sql_ticket_summary=ticket_text,
    )
    mock_client = _create_mock_gemini_client({
        "answer": "Yes, Ticket #101 previously recorded this issue, resolved by reinstalling the certificate.",
        "grounded": True,
        "confidence": 0.9,
        "evidence_used": ["Ticket #101"],
    })

    result = generate_grounded_response(
        query="Has this GlobalProtect issue happened before?",
        evidence=evidence,
        client=mock_client,
    )

    # Verify Gemini was invoked
    mock_client.models.generate_content.assert_called_once()
    call_args = mock_client.models.generate_content.call_args
    # NOTE: careful with operator precedence — `a or b if c else d` parses as
    # `(a or b) if c else d`. Use an explicit conditional here.
    if call_args.kwargs.get("contents") is not None:
        prompt_sent = call_args.kwargs.get("contents")
    elif call_args.args:
        prompt_sent = call_args.args[0]
    else:
        prompt_sent = ""
    assert "Ticket #101: GlobalProtect connection failure" in str(prompt_sent)
    assert result.grounded is True
    assert "Ticket #101" in result.answer


# ---------------------------------------------------------------------------
# Test C: Grounded error response
# ---------------------------------------------------------------------------

def test_c_grounded_error_response():
    """Provide exact ERR_VPN_AUTH_401 evidence, verify response can reference it."""
    evidence = EvidenceBundle(
        query="I am receiving ERR_VPN_AUTH_401",
        extracted_error_code="ERR_VPN_AUTH_401",
        rag_docs=[{
            "title": "VPN Gateway Troubleshooting",
            "category": "Network",
            "content": (
                "Error ERR_VPN_AUTH_401 indicates SSL handshake failure.\n"
                "1. Flush DNS cache using ipconfig /flushdns.\n"
                "2. Reinstall certificate."
            ),
        }],
    )
    mock_client = _create_mock_gemini_client({
        "answer": "ERR_VPN_AUTH_401 indicates SSL handshake failure. Flush DNS cache and reinstall certificate.",
        "grounded": True,
        "confidence": 0.95,
        "evidence_used": ["VPN Gateway Troubleshooting"],
    })

    result = generate_grounded_response(
        query="I am receiving ERR_VPN_AUTH_401",
        evidence=evidence,
        client=mock_client,
    )

    assert "ERR_VPN_AUTH_401" in result.answer
    assert result.grounded is True
    assert result.confidence == 0.95


# ---------------------------------------------------------------------------
# Test D: Unknown error code
# ---------------------------------------------------------------------------

def test_d_unknown_error_code_preserves_grounding():
    """
    Query: ERR_NETWORK_500. Evidence contains only ERR_VPN_AUTH_401.
    Verify response does NOT claim ERR_VPN_AUTH_401 diagnoses ERR_NETWORK_500.
    """
    evidence = EvidenceBundle(
        query="I am getting ERR_NETWORK_500 when connecting to VPN",
        extracted_error_code="ERR_NETWORK_500",
        rag_docs=[{
            "title": "GlobalProtect VPN Gateway Solutions",
            "category": "Network",
            "content": (
                "Error ERR_VPN_AUTH_401 indicates SSL handshake failure.\n"
                "1. Flush DNS cache using ipconfig /flushdns.\n"
                "2. Download and reinstall ACME-Root-CA-2026.crt certificate."
            ),
        }],
    )

    # Sub-case 1: Gemini correctly follows system prompt instructions
    mock_client_compliant = _create_mock_gemini_client({
        "answer": (
            "No specific documentation or evidence was found for error code ERR_NETWORK_500 "
            "in the knowledge base. Please contact your IT administrator."
        ),
        "grounded": False,
        "confidence": 0.0,
        "evidence_used": [],
    })
    res_compliant = generate_grounded_response(
        query="I am getting ERR_NETWORK_500 when connecting to VPN",
        evidence=evidence,
        client=mock_client_compliant,
    )
    assert "ERR_VPN_AUTH_401 indicates" not in res_compliant.answer
    assert "ERR_NETWORK_500" in res_compliant.answer

    # Sub-case 2: Gemini attempts to falsely substitute ERR_VPN_AUTH_401 for ERR_NETWORK_500
    mock_client_hallucinating = _create_mock_gemini_client({
        "answer": (
            "ERR_VPN_AUTH_401 indicates SSL handshake failure and diagnoses your issue. "
            "Flush DNS cache using ipconfig /flushdns to fix ERR_NETWORK_500."
        ),
        "grounded": True,
        "confidence": 0.9,
        "evidence_used": ["GlobalProtect VPN Gateway Solutions"],
    })
    res_rejected = generate_grounded_response(
        query="I am getting ERR_NETWORK_500 when connecting to VPN",
        evidence=evidence,
        client=mock_client_hallucinating,
    )
    # The substitution is caught by semantic validation and falls back to deterministic answer
    assert "No specific documentation match found for error code `ERR_NETWORK_500`" in res_rejected.answer
    assert "No grounded troubleshooting procedure was found for `ERR_NETWORK_500`" in res_rejected.answer


# ---------------------------------------------------------------------------
# Test E: No evidence behavior
# ---------------------------------------------------------------------------

def test_e_no_evidence_does_not_call_gemini():
    """Verify Gemini is not called when there is no usable evidence, and conservative msg is returned."""
    empty_evidence = EvidenceBundle(
        query="How do I fix my screen flickering?",
        rag_docs=[],
        tickets=[],
        error_logs=[],
        sql_ticket_summary="No support tickets match the given criteria.",
        sql_log_summary="No matching error logs found.",
    )
    mock_client = MagicMock()

    result = generate_grounded_response(
        query="How do I fix my screen flickering?",
        evidence=empty_evidence,
        client=mock_client,
    )

    # Gemini must NOT be called
    mock_client.models.generate_content.assert_not_called()
    assert NO_GROUNDED_PROCEDURE_MSG in result.answer
    assert result.grounded is False
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Test F: Gemini failure fallback
# ---------------------------------------------------------------------------

def test_f_gemini_failure_returns_deterministic_fallback():
    """Mock Gemini exception; verify deterministic grounded fallback is returned."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Gemini API connection error")

    evidence = EvidenceBundle(
        query="How do I troubleshoot VPN?",
        rag_docs=[{
            "title": "VPN Guide",
            "category": "Network",
            "content": "1. Check internet connection.\n2. Reconnect VPN.",
            "search_type": "text",
            "score": 0.9,
        }],
    )

    result = generate_grounded_response(
        query="How do I troubleshoot VPN?",
        evidence=evidence,
        client=mock_client,
    )

    # Fallback must be returned without crashing
    assert result is not None
    assert "Technical Documentation (RAG)" in result.answer
    assert "Check internet connection." in result.answer
    assert result.grounded is True


# ---------------------------------------------------------------------------
# Test G: Malformed Gemini response
# ---------------------------------------------------------------------------

def test_g_malformed_gemini_response_triggers_fallback():
    """Verify malformed JSON from Gemini triggers deterministic fallback."""
    mock_client = _create_mock_gemini_client("This is completely invalid JSON {{{{")
    evidence = EvidenceBundle(
        query="How to fix VPN?",
        rag_docs=[{
            "title": "VPN Guide",
            "category": "Network",
            "content": "1. Flush DNS cache.\n2. Restart client.",
            "search_type": "text",
        }],
    )

    result = generate_grounded_response(
        query="How to fix VPN?",
        evidence=evidence,
        client=mock_client,
    )

    assert result is not None
    assert "Technical Documentation (RAG)" in result.answer
    assert "Flush DNS cache." in result.answer


# ---------------------------------------------------------------------------
# Test H: Invalid confidence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_confidence", [-0.5, 1.5, 2.0, "high", None])
def test_h_invalid_confidence_triggers_fallback(bad_confidence):
    """Verify confidence out of 0.0-1.0 range triggers deterministic fallback."""
    mock_client = _create_mock_gemini_client({
        "answer": "Test answer",
        "grounded": True,
        "confidence": bad_confidence,
        "evidence_used": ["VPN Guide"],
    })
    evidence = EvidenceBundle(
        query="How to fix VPN?",
        rag_docs=[{
            "title": "VPN Guide",
            "category": "Network",
            "content": "1. Step one.\n2. Step two.",
            "search_type": "text",
        }],
    )

    result = generate_grounded_response(
        query="How to fix VPN?",
        evidence=evidence,
        client=mock_client,
    )

    assert result is not None
    assert "Technical Documentation (RAG)" in result.answer


# ---------------------------------------------------------------------------
# Test I: Unsupported troubleshooting
# ---------------------------------------------------------------------------

def test_i_unsupported_troubleshooting_rejected():
    """
    Give evidence that contains no troubleshooting steps.
    Verify Gemini cannot manufacture unsupported steps.
    """
    evidence = EvidenceBundle(
        query="How do I fix the server issue?",
        rag_docs=[{
            "title": "Server Policy",
            "category": "Policy",
            "content": "Server maintenance notice: Scheduled for Sunday 2 AM.",
            "search_type": "text",
        }],
    )
    # Gemini attempts to fabricate steps
    mock_client = _create_mock_gemini_client({
        "answer": (
            "Recommended troubleshooting steps:\n"
            "1. Reboot the main server node.\n"
            "2. Reconfigure database replication.\n"
            "3. Flush ARP cache."
        ),
        "grounded": True,
        "confidence": 0.9,
        "evidence_used": ["Server Policy"],
    })

    result = generate_grounded_response(
        query="How do I fix the server issue?",
        evidence=evidence,
        client=mock_client,
    )

    # Fabricated steps are rejected and fallback is returned with the conservative msg
    assert "Reboot the main server node" not in result.answer
    assert NO_GROUNDED_PROCEDURE_MSG in result.answer


# ---------------------------------------------------------------------------
# Test J: General documentation framing
# ---------------------------------------------------------------------------

def test_j_general_documentation_framing():
    """
    Provide a general VPN guide; verify response labels/frames it as general guidance
    rather than claiming a specific diagnosis.
    """
    evidence = EvidenceBundle(
        query="How can I troubleshoot VPN connectivity?",
        rag_docs=[{
            "title": "General VPN Connectivity Guide",
            "category": "Network",
            "content": (
                "General VPN Troubleshooting Guide:\n"
                "1. Verify active Wi-Fi connection.\n"
                "2. Restart GlobalProtect client software."
            ),
            "search_type": "text",
        }],
    )
    mock_client = _create_mock_gemini_client({
        "answer": (
            "Summary: General reference documentation for VPN connectivity troubleshooting.\n"
            "Recommended steps:\n"
            "1. Verify active Wi-Fi connection.\n"
            "2. Restart GlobalProtect client software.\n"
            "Source: General VPN Connectivity Guide (General Reference)"
        ),
        "grounded": True,
        "confidence": 0.88,
        "evidence_used": ["General VPN Connectivity Guide"],
    })

    result = generate_grounded_response(
        query="How can I troubleshoot VPN connectivity?",
        evidence=evidence,
        client=mock_client,
    )

    assert "General Reference" in result.answer or "General" in result.answer
    assert "Your VPN authentication is failing" not in result.answer
    assert "Verify active Wi-Fi connection" in result.answer


# ---------------------------------------------------------------------------
# Test K: Agent integration
# ---------------------------------------------------------------------------

def test_k_agent_integration_retrieval_to_response_generator(db_session):
    """
    Run an IT_SUPPORT query through build_and_run_agent with mocked Gemini.
    Verify: retrieval -> evidence bundle -> response generator occurs correctly.
    """
    rag = RAGService(db_session)
    rag.ingest_document(
        title="ACME VPN Client Setup",
        category="Network",
        content=(
            "VPN Setup Instructions:\n"
            "1. Open ACME VPN client.\n"
            "2. Enter gateway portal.acme.com.\n"
            "3. Connect using corporate credentials."
        ),
        file_type="txt",
    )

    synthesized_answer = (
        "Summary: Setup instructions from ACME VPN Client Setup guide.\n"
        "Recommended steps:\n"
        "1. Open ACME VPN client.\n"
        "2. Enter gateway portal.acme.com.\n"
        "3. Connect using corporate credentials."
    )
    mock_client = _create_mock_gemini_client({
        "answer": synthesized_answer,
        "grounded": True,
        "confidence": 0.95,
        "evidence_used": ["ACME VPN Client Setup"],
    })

    res = build_and_run_agent(
        db_session,
        "How do I setup the VPN client?",
        gemini_client=mock_client,
    )

    # 1. Retrieval succeeded and populates metadata
    assert len(res.rag_sources) > 0
    assert len(res.tools_used) > 0
    # 2. Gemini was called with evidence
    mock_client.models.generate_content.assert_called()
    # 3. ChatResponse contains the synthesized response
    assert res.answer == synthesized_answer


# ---------------------------------------------------------------------------
# Test L: Casual isolation
# ---------------------------------------------------------------------------

def test_l_casual_isolation(db_session):
    """Verify response generator is NOT called for CASUAL queries."""
    with patch("app.agents.agent_graph.generate_grounded_response") as mock_gen:
        res = build_and_run_agent(db_session, "Hello! How are you?")
        mock_gen.assert_not_called()
        assert "How can I help you with an IT issue?" in res.answer
        assert len(res.tools_used) == 0


# ---------------------------------------------------------------------------
# Test M: General isolation
# ---------------------------------------------------------------------------

def test_m_general_isolation(db_session):
    """Verify response generator is NOT called for GENERAL queries."""
    with patch("app.agents.agent_graph.generate_grounded_response") as mock_gen:
        res = build_and_run_agent(db_session, "Write a Python function to sort a list")
        mock_gen.assert_not_called()
        assert "general programming" in res.answer.lower()
        assert len(res.tools_used) == 0


# ---------------------------------------------------------------------------
# Test N: Ambiguous isolation
# ---------------------------------------------------------------------------

def test_n_ambiguous_isolation(db_session):
    """Verify response generator is NOT called for AMBIGUOUS queries."""
    with patch("app.agents.agent_graph.generate_grounded_response") as mock_gen:
        res = build_and_run_agent(db_session, "What should I do?")
        mock_gen.assert_not_called()
        assert "Could you please provide more details" in res.answer
        assert len(res.tools_used) == 0


# ---------------------------------------------------------------------------
# Additional Unit & Edge Case Tests
# ---------------------------------------------------------------------------

def test_evidence_bundle_dict_input():
    """Verify generate_grounded_response accepts a plain dict for evidence."""
    dict_evidence = {
        "query": "VPN issue",
        "rag_docs": [{
            "title": "VPN Guide",
            "category": "Network",
            "content": "1. Flush DNS.",
        }],
    }
    mock_client = _create_mock_gemini_client({
        "answer": "Flush DNS.",
        "grounded": True,
        "confidence": 0.9,
        "evidence_used": ["VPN Guide"],
    })
    result = generate_grounded_response("VPN issue", dict_evidence, client=mock_client)
    assert result.answer == "Flush DNS."


def test_get_gemini_client_none_without_key():
    """Verify get_gemini_client returns None when GEMINI_API_KEY is not configured."""
    with patch("app.agents.response_generator.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = None
        with patch.dict("os.environ", {}, clear=True):
            client = get_gemini_client()
            assert client is None
