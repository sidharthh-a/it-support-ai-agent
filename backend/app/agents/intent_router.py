"""
Gemini-backed Intent Router for the IT Support AI Agent.

Architecture:
1. Deterministic safety overrides (error codes, explicit ticket actions)
   -> Immediately classified as IT_SUPPORT without calling Gemini.
2. Gemini Intent Router (LLM classification)
   -> Structured classification into CASUAL, GENERAL, IT_SUPPORT, or AMBIGUOUS.
3. Deterministic fallback
   -> If Gemini is unavailable, errors out, or returns invalid/malformed output,
      falls back safely to existing deterministic classifiers.
"""

from enum import Enum
import json
import os
import re
from typing import Any, Optional
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.logging import logger

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None


class QueryIntent(str, Enum):
    CASUAL = "casual"
    GENERAL = "general"
    IT_SUPPORT = "it_support"
    AMBIGUOUS = "ambiguous"


class IntentResult(BaseModel):
    intent: QueryIntent
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str


# ---------------------------------------------------------------------------
# Deterministic Safety Overrides
# ---------------------------------------------------------------------------

# Error-code patterns (ERR_*, ERROR_*, etc.)
_ERROR_CODE_REGEX = re.compile(r"\bERR(?:OR)?_[A-Z0-9_]+\b", re.IGNORECASE)

# Explicit ticket action phrases
_TICKET_ACTION_REGEX = re.compile(
    r"\b(create|open|raise|submit|close|update)\s+(?:a\s+|an\s+|the\s+)?ticket\b",
    re.IGNORECASE,
)


def check_safety_override(query: str) -> Optional[IntentResult]:
    """
    Check if the query matches hard IT-support requirements that must never
    be misclassified or overridden by an LLM.
    """
    q = query.strip()
    if not q:
        return None

    # Error code override (e.g. ERR_VPN_AUTH_401)
    if _ERROR_CODE_REGEX.search(q):
        return IntentResult(
            intent=QueryIntent.IT_SUPPORT,
            confidence=1.0,
            reason="Deterministic safety override: explicit error code pattern detected",
        )

    # Explicit ticket actions
    if _TICKET_ACTION_REGEX.search(q):
        return IntentResult(
            intent=QueryIntent.IT_SUPPORT,
            confidence=1.0,
            reason="Deterministic safety override: explicit ticket action requested",
        )

    return None


# ---------------------------------------------------------------------------
# Gemini Client & Classification
# ---------------------------------------------------------------------------

CLASSIFICATION_PROMPT_TEMPLATE = """You are an IT support query intent classifier.
Classify the following user query into exactly ONE of these four categories:
- casual: greetings, thanks, small talk, casual conversation
- general: general factual questions, programming questions, computer science, general technical concepts not related to IT support incidents
- it_support: laptop/device/desktop/monitor issues, Wi-Fi/network/VPN issues, login/access/password/MFA problems, software/hardware failures, error messages, incidents, troubleshooting, support tickets, IT operational problems
- ambiguous: insufficient information to confidently determine intent

User Query: "{query}"

Respond with ONLY a JSON object in this exact schema:
{{"intent": "casual"|"general"|"it_support"|"ambiguous", "confidence": <float between 0.0 and 1.0>, "reason": "<short explanation>"}}
"""


def get_gemini_client() -> Optional[Any]:
    """Initialize a Google GenAI client if GEMINI_API_KEY is available."""
    if genai is None:
        return None

    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception as exc:
        logger.warning("Gemini client initialization failed: %s", type(exc).__name__)
        return None


def _parse_and_validate_gemini_output(response_obj: Any) -> IntentResult:
    """Extract, parse, and strictly validate Gemini structured output."""
    if isinstance(response_obj, str):
        raw_text = response_obj
    elif hasattr(response_obj, "text") and isinstance(response_obj.text, str):
        raw_text = response_obj.text
    elif isinstance(response_obj, dict):
        return IntentResult.model_validate(response_obj)
    else:
        raise ValueError(f"Unsupported Gemini response type: {type(response_obj)}")

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Gemini output did not parse into a JSON object")

    return IntentResult.model_validate(data)


def _call_gemini_classification(
    client: Any, query: str, model_name: Optional[str] = None
) -> IntentResult:
    """Execute Gemini generate_content call and validate structured output."""
    model = model_name or settings.GEMINI_MODEL
    prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(query=query)

    config_args = {
        "response_mime_type": "application/json",
        "response_schema": IntentResult,
        "temperature": 0.0,
    }
    config = types.GenerateContentConfig(**config_args) if types is not None else None

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return _parse_and_validate_gemini_output(response)


# ---------------------------------------------------------------------------
# Fallback Classification
# ---------------------------------------------------------------------------

def classify_query_domain(query: str) -> str:
    """
    Expose classify_query_domain in the intent_router namespace by delegating
    to agent_graph, enabling deterministic fallback and test patching.
    """
    from app.agents.agent_graph import classify_query_domain as _cqd
    return _cqd(query)


def is_greeting_or_casual_query(query: str) -> bool:
    """
    Expose is_greeting_or_casual_query in the intent_router namespace by delegating
    to agent_graph.
    """
    from app.agents.agent_graph import is_greeting_or_casual_query as _igq
    return _igq(query)


def _deterministic_fallback(query: str) -> IntentResult:
    """
    Deterministic fallback calling existing classifiers when Gemini is unavailable
    or fails validation.
    """
    if is_greeting_or_casual_query(query):
        return IntentResult(
            intent=QueryIntent.CASUAL,
            confidence=0.9,
            reason="Deterministic fallback: greeting/casual query detected",
        )

    domain = classify_query_domain(query)
    if domain == "it_support":
        return IntentResult(
            intent=QueryIntent.IT_SUPPORT,
            confidence=0.8,
            reason="Deterministic fallback: classify_query_domain -> it_support",
        )
    elif domain == "general":
        return IntentResult(
            intent=QueryIntent.GENERAL,
            confidence=0.8,
            reason="Deterministic fallback: classify_query_domain -> general",
        )
    else:
        return IntentResult(
            intent=QueryIntent.AMBIGUOUS,
            confidence=0.5,
            reason="Deterministic fallback: classify_query_domain -> ambiguous",
        )


# ---------------------------------------------------------------------------
# Public Routing Interface
# ---------------------------------------------------------------------------

def route_query(
    query: str,
    client: Optional[Any] = None,
    model_name: Optional[str] = None,
) -> IntentResult:
    """
    Public entrypoint for routing user queries.

    1. Deterministic safety overrides are evaluated first.
    2. Gemini intent routing is attempted if client is available or configured.
    3. Deterministic fallback is used on any Gemini failure or validation error.
    """
    if not query or not query.strip():
        return IntentResult(
            intent=QueryIntent.AMBIGUOUS,
            confidence=1.0,
            reason="Empty query",
        )

    # 1. Deterministic safety overrides
    safety_override = check_safety_override(query)
    if safety_override is not None:
        logger.debug("Intent router: safety override applied: %s", safety_override.intent)
        return safety_override

    # 2. Gemini classification
    active_client = client or get_gemini_client()
    if active_client is not None:
        try:
            return _call_gemini_classification(active_client, query, model_name=model_name)
        except Exception as exc:
            logger.warning(
                "Gemini classification failed (%s); using deterministic fallback",
                type(exc).__name__,
            )

    # 3. Deterministic fallback
    return _deterministic_fallback(query)
