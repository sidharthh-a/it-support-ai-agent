"""
Tests for Gemini Intent Router (Phase 2 Step 2.1).

All Gemini calls are mocked; zero live Gemini API calls are made.
Tests deterministic safety overrides, Gemini structured output validation,
and seamless fallback to existing deterministic classifiers.
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError

from app.agents.intent_router import (
    QueryIntent,
    IntentResult,
    route_query,
    check_safety_override,
    _parse_and_validate_gemini_output,
)
from app.agents.agent_graph import build_and_run_agent


def _create_mock_gemini_client(response_text: str):
    """Helper to produce a mock Google GenAI client returning response_text."""
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = response_text
    client.models.generate_content.return_value = mock_resp
    return client


# ---------------------------------------------------------------------------
# TEST 1 — CASUAL
# ---------------------------------------------------------------------------

def test_1_casual_intent():
    """Mock Gemini returns casual intent; verify QueryIntent.CASUAL is returned."""
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "casual",
            "confidence": 0.98,
            "reason": "Greeting"
        })
    )
    result = route_query("hello", client=mock_client)
    assert result.intent == QueryIntent.CASUAL
    assert result.confidence == 0.98
    assert result.reason == "Greeting"
    mock_client.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# TEST 2 — GENERAL
# ---------------------------------------------------------------------------

def test_2_general_intent():
    """Mock Gemini returns general intent; verify QueryIntent.GENERAL is returned."""
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "general",
            "confidence": 0.95,
            "reason": "General computer science question"
        })
    )
    result = route_query("What is machine learning?", client=mock_client)
    assert result.intent == QueryIntent.GENERAL
    assert result.confidence == 0.95
    assert result.reason == "General computer science question"
    mock_client.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# TEST 3 — IT_SUPPORT
# ---------------------------------------------------------------------------

def test_3_it_support_intent():
    """Mock Gemini returns IT_SUPPORT; verify QueryIntent.IT_SUPPORT is returned."""
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "it_support",
            "confidence": 0.99,
            "reason": "Network connectivity issue on laptop"
        })
    )
    result = route_query("My laptop cannot connect to Wi-Fi", client=mock_client)
    assert result.intent == QueryIntent.IT_SUPPORT
    assert result.confidence == 0.99
    assert "Network connectivity" in result.reason
    mock_client.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# TEST 4 — AMBIGUOUS
# ---------------------------------------------------------------------------

def test_4_ambiguous_intent():
    """Mock Gemini returns ambiguous; verify QueryIntent.AMBIGUOUS is returned."""
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "ambiguous",
            "confidence": 0.50,
            "reason": "Insufficient information to determine specific issue"
        })
    )
    result = route_query("Can you help me?", client=mock_client)
    assert result.intent == QueryIntent.AMBIGUOUS
    assert result.confidence == 0.50
    mock_client.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# TEST 5 — GEMINI FAILURE (FALLBACK TO classify_query_domain)
# ---------------------------------------------------------------------------

def test_5_gemini_failure_falls_back_to_classify_query_domain():
    """
    When Gemini raises an exception, route_query() must fall back to
    classify_query_domain() and preserve the deterministic classification.
    """
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Gemini API connection error 500")

    with patch("app.agents.intent_router.classify_query_domain") as mock_classify:
        mock_classify.return_value = "it_support"
        result = route_query("Screen resolution glitch", client=mock_client)
        mock_classify.assert_called_once_with("Screen resolution glitch")
        assert result.intent == QueryIntent.IT_SUPPORT
        assert "fallback" in result.reason.lower()


# ---------------------------------------------------------------------------
# TEST 6 — MALFORMED RESPONSE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_output", [
    "I cannot classify this right now.",
    "{malformed json",
    "",
    "```json\n[1, 2, 3]\n```",
    "42",
])
def test_6_malformed_response_triggers_fallback(bad_output):
    """Malformed or non-JSON Gemini responses must fall back cleanly."""
    mock_client = _create_mock_gemini_client(bad_output)
    # Using a general query that deterministic routing recognizes
    result = route_query("how to reverse a list", client=mock_client)
    assert result.intent == QueryIntent.GENERAL
    assert "fallback" in result.reason.lower()


# ---------------------------------------------------------------------------
# TEST 7 — INVALID INTENT
# ---------------------------------------------------------------------------

def test_7_invalid_intent_triggers_fallback():
    """If Gemini returns an unknown intent string, router falls back."""
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "billing_and_sales",
            "confidence": 0.99,
            "reason": "Unknown domain"
        })
    )
    result = route_query("explain recursion with an example", client=mock_client)
    assert result.intent == QueryIntent.GENERAL
    assert "fallback" in result.reason.lower()


# ---------------------------------------------------------------------------
# TEST 8 — INVALID CONFIDENCE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("invalid_confidence", [
    -0.5,
    1.5,
    2.0,
    "high",
    None,
])
def test_8_invalid_confidence_triggers_fallback(invalid_confidence):
    """Confidence outside [0.0, 1.0] or non-numeric must trigger fallback."""
    payload = {
        "intent": "general",
        "confidence": invalid_confidence,
        "reason": "Test confidence"
    }
    mock_client = _create_mock_gemini_client(json.dumps(payload))
    result = route_query("what is dynamic programming", client=mock_client)
    assert result.intent == QueryIntent.GENERAL
    assert "fallback" in result.reason.lower()


# ---------------------------------------------------------------------------
# TEST 9 — ERROR CODE OVERRIDE
# ---------------------------------------------------------------------------

def test_9_error_code_override():
    """
    Error code patterns (e.g. ERR_VPN_AUTH_401) must immediately become
    IT_SUPPORT. Gemini must NOT be called and cannot override this.
    """
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "general",
            "confidence": 0.99,
            "reason": "Misclassified as general"
        })
    )
    result = route_query("ERR_VPN_AUTH_401", client=mock_client)
    assert result.intent == QueryIntent.IT_SUPPORT
    assert result.confidence == 1.0
    assert "error code" in result.reason.lower()
    # Gemini must NOT have been called
    mock_client.models.generate_content.assert_not_called()


# ---------------------------------------------------------------------------
# TEST 10 — TICKET OVERRIDE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ticket_query", [
    "Create a ticket for my laptop",
    "open a ticket for broken screen",
    "raise a ticket for network outage",
    "submit a ticket",
    "close a ticket TICK-101",
    "update a ticket TICK-102",
])
def test_10_ticket_override(ticket_query):
    """
    Explicit ticket actions must remain IT_SUPPORT without Gemini override.
    """
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "casual",
            "confidence": 0.99,
            "reason": "Attempted override"
        })
    )
    result = route_query(ticket_query, client=mock_client)
    assert result.intent == QueryIntent.IT_SUPPORT
    assert result.confidence == 1.0
    assert "ticket" in result.reason.lower()
    mock_client.models.generate_content.assert_not_called()


# ---------------------------------------------------------------------------
# TEST 11 — NORMAL FALLBACK PRESERVES DETERMINISTIC CLASSIFICATION
# ---------------------------------------------------------------------------

def test_11_normal_fallback_preserves_deterministic_behavior():
    """
    When Gemini fails or is unavailable, verify deterministic classifications
    are strictly preserved for IT, General, and Casual queries.
    """
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = ConnectionResetError("Remote disconnected")

    # 1. IT support query handled deterministically
    it_res = route_query("DNS lookup is failing for internal sites", client=mock_client)
    assert it_res.intent == QueryIntent.IT_SUPPORT

    # 2. General query handled deterministically
    gen_res = route_query("what is the time complexity of quicksort", client=mock_client)
    assert gen_res.intent == QueryIntent.GENERAL

    # 3. Greeting query handled deterministically
    casual_res = route_query("hello", client=mock_client)
    assert casual_res.intent == QueryIntent.CASUAL

    # 4. Ambiguous query handled deterministically
    amb_res = route_query("how to debug", client=mock_client)
    assert amb_res.intent in (QueryIntent.AMBIGUOUS, QueryIntent.IT_SUPPORT)


# ---------------------------------------------------------------------------
# ADDITIONAL UNIT TESTS: EDGE CASES & VALIDATION
# ---------------------------------------------------------------------------

def test_safety_override_helper_empty():
    """Empty or whitespace strings return None from check_safety_override."""
    assert check_safety_override("") is None
    assert check_safety_override("   ") is None


def test_empty_query_route_query():
    """Empty queries are routed safely to AMBIGUOUS without errors."""
    res = route_query("")
    assert res.intent == QueryIntent.AMBIGUOUS
    assert res.confidence == 1.0


def test_clean_fenced_markdown_gemini_output():
    """Markdown code fences (```json ... ```) must be parsed cleanly."""
    fenced_json = "```json\n{\"intent\": \"general\", \"confidence\": 0.88, \"reason\": \"Coding question\"}\n```"
    result = _parse_and_validate_gemini_output(fenced_json)
    assert result.intent == QueryIntent.GENERAL
    assert result.confidence == 0.88


def test_agent_graph_integration_with_gemini_casual(db_session):
    """
    Integration test: agent graph respects Gemini CASUAL classification
    and returns casual greeting response without invoking tools.
    """
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "casual",
            "confidence": 0.95,
            "reason": "Casual smalltalk"
        })
    )
    with patch("app.agents.intent_router.get_gemini_client", return_value=mock_client):
        res = build_and_run_agent(db_session, "Good afternoon assistant!")
        assert "Hey! How can I help you with an IT issue?" in res.answer
        assert res.tools_used == []
        assert res.rag_sources == []
        assert res.sql_sources == []


def test_agent_graph_integration_with_gemini_general(db_session):
    """
    Integration test: agent graph respects Gemini GENERAL classification
    and returns general domain response without invoking tools.
    """
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "general",
            "confidence": 0.95,
            "reason": "Unrelated history question"
        })
    )
    with patch("app.agents.intent_router.get_gemini_client", return_value=mock_client):
        res = build_and_run_agent(db_session, "Who was the first emperor of Rome?")
        assert "IT support assistant" in res.answer
        assert res.tools_used == []
        assert res.rag_sources == []
        assert res.sql_sources == []


def test_gemini_call_enforces_structured_schema():
    """
    Regression test: Verify that _call_gemini_classification configures
    response_schema=IntentResult and response_mime_type='application/json'
    in GenerateContentConfig so Gemini API strictly validates output structure.
    """
    from app.agents.intent_router import _call_gemini_classification

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "intent": "it_support",
        "confidence": 0.95,
        "reason": "Structured schema test"
    })
    mock_client.models.generate_content.return_value = mock_resp

    result = _call_gemini_classification(mock_client, "Outlook won't sync email")
    assert result.intent == QueryIntent.IT_SUPPORT

    mock_client.models.generate_content.assert_called_once()
    _, kwargs = mock_client.models.generate_content.call_args
    passed_config = kwargs.get("config")
    assert passed_config is not None
    assert passed_config.response_mime_type == "application/json"
    assert passed_config.response_schema == IntentResult


def test_agent_graph_integration_with_gemini_ambiguous(db_session):
    """
    Regression test: When Gemini returns AMBIGUOUS (e.g. 'Can you help me?'),
    agent graph must NOT trigger RAG, SQL retrieval, or IT troubleshooting tools.
    """
    mock_client = _create_mock_gemini_client(
        json.dumps({
            "intent": "ambiguous",
            "confidence": 0.50,
            "reason": "Vague greeting/assistance request"
        })
    )
    with patch("app.agents.intent_router.get_gemini_client", return_value=mock_client):
        res = build_and_run_agent(db_session, "Can you help me?")
        assert res.tools_used == []
        assert res.rag_sources == []
        assert res.sql_sources == []
        assert res.ticket_created is None
        assert res.ticket_updated is None
        assert "provide more details" in res.answer.lower() or "describe the specific issue" in res.answer.lower()


@pytest.mark.parametrize("ambiguous_query", [
    "What should I do?",
    "My computer",
    "I need help",
])
def test_agent_graph_ambiguous_queries_fallback_safe(db_session, ambiguous_query):
    """
    Regression test: Ambiguous queries under fallback must safely return
    clarification without triggering RAG, SQL tools, or ticket actions.
    """
    res = build_and_run_agent(db_session, ambiguous_query)
    assert res.tools_used == []
    assert res.rag_sources == []
    assert res.sql_sources == []
    assert res.ticket_created is None
    assert res.ticket_updated is None

