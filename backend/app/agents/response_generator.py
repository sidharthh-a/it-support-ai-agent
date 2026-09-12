"""
Grounded Gemini Response Synthesis Layer for IT Support Queries.

Architecture:
1. Receives original query and retrieved evidence bundle (RAG docs, historical tickets, error logs, tool results).
2. If no meaningful evidence is present, immediately returns conservative no-grounded-procedure
   behavior without invoking Gemini.
3. Invokes Gemini with strict grounding instructions and enforces structured output (GroundedResponse).
4. Validates that output is strictly grounded (exact error code match, no fabricated steps).
5. If Gemini fails, times out, is unavailable, or produces invalid output, safely falls back
   to deterministic grounded response assembly.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.logging import logger
from app.tools.agent_tools import extract_error_code

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None


# ---------------------------------------------------------------------------
# Constants & Models
# ---------------------------------------------------------------------------

NO_GROUNDED_PROCEDURE_MSG = (
    "No grounded troubleshooting procedure was found in the knowledge base. "
    "Please contact your IT administrator or submit an IT support ticket."
)

RAG_RELEVANCE_THRESHOLD = 0.35

# Common words ignored when computing lexical overlap between a query and a
# text-fallback document.  Text-fallback (keyword) hits carry score 0.0, so a
# deterministic token-overlap gate decides whether the document is topically
# relevant enough to ground troubleshooting steps.
_TOKEN_OVERLAP_STOPWORDS = {
    "the", "and", "for", "with", "how", "what", "when", "why", "can", "you",
    "your", "not", "are", "was", "this", "that", "have", "has", "did", "does",
    "get", "got", "fix", "its", "from", "into", "onto", "out", "off", "all",
    "any", "some", "more", "most", "very", "just", "also", "been", "being",
    "were", "will", "would", "should", "could", "there", "their", "them",
    "then", "than", "who", "whom", "which", "where", "again", "before",
    "after", "about", "won", "dont", "didn", "cant", "wont", "isnt", "arent",
}


def _tokenize_for_overlap(text: str) -> set:
    return {
        t for t in re.findall(r"[a-z0-9]+", text.lower())
        if len(t) > 2 and t not in _TOKEN_OVERLAP_STOPWORDS
    }


def _doc_relevant_for_text_fallback(query: str, doc: Dict[str, Any]) -> bool:
    """Decide whether a keyword text-fallback document is topically relevant.

    Vector results are already gated by cosine similarity; text-fallback hits
    (score 0.0) require lexical overlap between query tokens and the document.
    """
    query_tokens = _tokenize_for_overlap(query)
    if not query_tokens:
        return False
    doc_tokens = _tokenize_for_overlap(
        doc.get("title", "") + " " + doc.get("content", "")
    )
    return bool(query_tokens & doc_tokens)


class GroundedResponse(BaseModel):
    answer: str
    grounded: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_used: List[str] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    query: str
    extracted_error_code: Optional[str] = None
    rag_docs: List[Dict[str, Any]] = Field(default_factory=list)
    tickets: List[str] = Field(default_factory=list)
    error_logs: List[str] = Field(default_factory=list)
    sql_ticket_summary: Optional[str] = None
    sql_log_summary: Optional[str] = None
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    auto_escalated: bool = False
    ticket_created_info: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Helpers for Snippet & Step Extraction (Isolated from agent_graph)
# ---------------------------------------------------------------------------

def get_clean_snippet(text: str, max_chars: int = 350) -> str:
    """Extract a clean snippet without cutting mid-word or mid-sentence."""
    text = text.strip()
    if len(text) <= max_chars:
        return text

    def _is_sentence_dot(s: str, pos: int) -> bool:
        return pos >= 0 and s[pos] == "." and (pos == 0 or not s[pos - 1].isdigit())

    search_end = min(len(text), max_chars + 200)
    forward_end = -1
    for i in range(max_chars - 1, search_end):
        if i >= len(text):
            break
        if text[i] == "." and _is_sentence_dot(text, i):
            after = text[i + 1] if i + 1 < len(text) else ""
            if after in ("", " ", "\n"):
                forward_end = i
                break

    if forward_end > 0:
        return text[: forward_end + 1].strip()

    truncated = text[:max_chars]
    best_dot = -1
    for pattern in (". ", ".\n"):
        pos = len(truncated)
        while True:
            pos = truncated.rfind(pattern, 0, pos)
            if pos < 0:
                break
            if _is_sentence_dot(truncated, pos):
                if pos > 100:
                    best_dot = max(best_dot, pos)
                break
            pos -= 1

    if best_dot > 100:
        return truncated[: best_dot + 1].strip()

    last_space = truncated.rfind(" ")
    if last_space > 100:
        return truncated[:last_space].strip() + "..."
    return truncated.strip()


def extract_troubleshooting_steps(content: str) -> List[str]:
    """Extract complete numbered or bulleted troubleshooting steps from document content.

    Handles both line-delimited steps and inline steps ("Intro. 1. Do X. 2. Do Y.")
    produced by the whitespace-normalising chunker.
    """
    steps = []
    raw_blocks = re.findall(
        r"(?:^|\n)\s*(\d+[\.\)]\s+.*?)(?=\n\s*\d+[\.\)]|\n\n|$)",
        content,
        re.DOTALL,
    )
    if not raw_blocks and re.search(r"(?<![\w.])\d+[\.\)]\s+", content):
        # Inline fallback: split on sentence boundaries before a numbered marker.
        # (?<=[.!?]) captures steps that start after a previous sentence ends.
        inline = re.findall(
            r"(?:^|(?<=[\.!\?]))\s*(\d+[\.\)]\s+.*?)(?=\s*(?:\d+[\.\)]\s+|$))",
            content,
        )
        if inline:
            raw_blocks = inline
    if raw_blocks:
        for b in raw_blocks:
            clean_step = " ".join(b.strip().split())
            if clean_step:
                steps.append(clean_step)

    if not steps:
        for line in content.split("\n"):
            stripped = line.strip()
            if re.match(r"^\d+[\.\)]\s+", stripped) or re.match(r"^[-*]\s+", stripped):
                steps.append(stripped)

    return steps[:6]


def has_usable_evidence(bundle: EvidenceBundle) -> bool:
    """Check if the evidence bundle contains any usable retrieval evidence."""
    for doc in bundle.rag_docs:
        content = doc.get("content", "").strip() if isinstance(doc, dict) else str(doc).strip()
        if content:
            return True

    for t in bundle.tickets:
        t_str = str(t).strip()
        if t_str and "No support tickets match" not in t_str:
            return True

    if bundle.sql_ticket_summary:
        s = bundle.sql_ticket_summary.strip()
        if s and "No support tickets match" not in s:
            return True

    for l in bundle.error_logs:
        l_str = str(l).strip()
        if l_str and "No matching error logs" not in l_str:
            return True

    if bundle.sql_log_summary:
        s = bundle.sql_log_summary.strip()
        if s and "No matching error logs" not in s:
            return True

    return False


# ---------------------------------------------------------------------------
# Prompting & Gemini Call
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTIONS = """You are a grounded IT support assistant response synthesizer.
Your task is to generate a concise, grounded technical support response for the user's query based ONLY on the supplied evidence bundle.

CRITICAL GROUNDING RULES:
1. Use ONLY the supplied evidence. The evidence is the sole source of truth.
2. Do NOT invent troubleshooting steps or procedures under any circumstances.
3. Do NOT invent error codes, ticket IDs, usernames, devices, or incidents.
4. Do NOT claim an exact diagnosis unless the evidence explicitly supports it.
5. If the user query specifies an exact error code (e.g., ERR_NETWORK_500), and the evidence does NOT contain that exact error code:
   - State clearly that no specific documentation or evidence was found for that error code.
   - Do NOT substitute the user's error code with a different error code found in the evidence (e.g. do not substitute ERR_VPN_AUTH_401).
   - Do NOT claim documentation for one error code diagnoses or applies to a different error code.
6. If the user asks a general IT question and retrieval returns a general guide:
   - Frame it clearly as a general reference or documented general procedure, NOT an exact confirmed diagnosis.
   - Clearly distinguish: documented general procedure, exact incident/error evidence, historical examples.
7. If evidence contains no troubleshooting steps, state that no troubleshooting steps are documented in the evidence. Never fabricate steps.
8. If the evidence is insufficient to resolve the issue, clearly state so and advise contacting IT support or submitting a ticket.
9. Never treat absence of evidence as evidence of a diagnosis.
10. Distinguish exact matches from general/reference information.

RESPONSE FORMAT:
Produce a concise response covering:
- Summary
- Evidence / likely cause (ONLY if supported by evidence)
- Recommended steps (ONLY from evidence)
- Source/context
- Escalation guidance when evidence is insufficient
Do not force sections that have no evidence. Do not make the answer unnecessarily verbose.
"""


def format_evidence_prompt(query: str, bundle: EvidenceBundle) -> str:
    """Format the query and retrieved evidence bundle into a structured prompt."""
    parts = [f"USER QUERY: {query}\n\nRETRIEVED EVIDENCE BUNDLE:"]

    # RAG docs
    if bundle.rag_docs:
        parts.append("--- Technical Documentation (RAG) ---")
        for idx, doc in enumerate(bundle.rag_docs, 1):
            title = doc.get("title", f"Document {idx}")
            category = doc.get("category", "General")
            content = doc.get("content", "")
            parts.append(f"Document [{idx}]: {title} (Category: {category})\nContent:\n{content}")
    else:
        parts.append("--- Technical Documentation (RAG) ---\nNo documentation found.")

    # SQL Tickets
    ticket_text = bundle.sql_ticket_summary or "\n".join(bundle.tickets)
    if ticket_text and "No support tickets match" not in ticket_text:
        parts.append(f"--- Historical Support Tickets (SQL) ---\n{ticket_text}")
    else:
        parts.append("--- Historical Support Tickets (SQL) ---\nNo matching historical tickets found.")

    # SQL Error Logs
    log_text = bundle.sql_log_summary or "\n".join(bundle.error_logs)
    if log_text and "No matching error logs" not in log_text:
        parts.append(f"--- System Error Logs (SQL) ---\n{log_text}")
    else:
        parts.append("--- System Error Logs (SQL) ---\nNo matching error logs found.")

    # Tool Results
    if bundle.tool_results:
        parts.append("--- Tool Execution Results ---")
        for t in bundle.tool_results:
            parts.append(f"- Tool {t.get('tool', 'unknown')}: {t.get('summary', '')}")

    return "\n\n".join(parts)


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


def _validate_grounded_response(
    resp: GroundedResponse,
    query: str,
    bundle: EvidenceBundle,
) -> GroundedResponse:
    """
    Validate that the generated response does not violate critical grounding constraints:
    1. Confidence must be between 0.0 and 1.0 (enforced by Pydantic schema).
    2. If user query specifies an error code (e.g. ERR_NETWORK_500), and evidence contains ONLY
       a different error code (e.g. ERR_VPN_AUTH_401), verify the response does NOT claim
       the evidence error diagnoses or fixes the query error code.
    3. If evidence has no troubleshooting steps and response fabricates steps, reject.
    """
    extracted_error = bundle.extracted_error_code or extract_error_code(query)
    if extracted_error:
        evidence_text = " ".join(
            [d.get("title", "") + " " + d.get("content", "") for d in bundle.rag_docs]
            + bundle.tickets
            + bundle.error_logs
            + [bundle.sql_ticket_summary or "", bundle.sql_log_summary or ""]
        )
        if extracted_error.lower() not in evidence_text.lower():
            # Query error code is NOT present in the evidence.
            # If the response mentions an unrelated error code from evidence, verify it does
            # not claim it diagnoses or resolves the query error.
            unrelated_error = extract_error_code(evidence_text)
            if unrelated_error and unrelated_error.lower() in resp.answer.lower():
                err_mentioned_negatively = any(
                    phrase in resp.answer.lower()
                    for phrase in [
                        "no specific documentation",
                        "no documentation",
                        "no grounded",
                        "no evidence",
                        "not found",
                        "does not match",
                    ]
                )
                if not err_mentioned_negatively:
                    raise ValueError(
                        f"Response substitutes unrelated error code {unrelated_error} for query error {extracted_error}"
                    )

    # Unsupported troubleshooting steps check.
    # The chunker normalises whitespace (newlines collapse to spaces), so evidence
    # steps may appear inline ("... 1. Do X. 2. Do Y.").  Normalise the answer the
    # same way before scanning so legitimate inline steps are recognised while
    # genuinely fabricated steps are still rejected.
    has_steps_in_evidence = any(
        bool(extract_troubleshooting_steps(re.sub(r"\s+", " ", d.get("content", ""))))
        for d in bundle.rag_docs
    )
    if not has_steps_in_evidence:
        normalized_answer = re.sub(r"\s+", " ", resp.answer)
        numbered_steps = re.findall(r"(?:^|[\.\n\?\!])\s*\d+[\.\)]\s+", normalized_answer)
        if len(numbered_steps) >= 2:
            raise ValueError("Response fabricates troubleshooting steps not present in evidence")

    return resp


def _parse_and_validate_gemini_output(
    response_obj: Any,
    query: str,
    bundle: EvidenceBundle,
) -> GroundedResponse:
    """Extract, parse, and strictly validate Gemini structured output."""
    if isinstance(response_obj, str):
        raw_text = response_obj
    elif hasattr(response_obj, "text") and isinstance(response_obj.text, str):
        raw_text = response_obj.text
    elif isinstance(response_obj, dict):
        raw_text = None
        data = response_obj
    else:
        raise ValueError(f"Unsupported Gemini response type: {type(response_obj)}")

    if raw_text is not None:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)

    if not isinstance(data, dict):
        raise ValueError("Gemini output did not parse into a JSON object")

    grounded_response = GroundedResponse.model_validate(data)
    return _validate_grounded_response(grounded_response, query, bundle)


def _call_gemini_generation(
    client: Any,
    query: str,
    bundle: EvidenceBundle,
    model_name: Optional[str] = None,
) -> GroundedResponse:
    """Execute Gemini generate_content call and validate structured output."""
    model = model_name or settings.GEMINI_MODEL
    prompt = format_evidence_prompt(query, bundle)

    config_args = {
        "system_instruction": SYSTEM_INSTRUCTIONS,
        "response_mime_type": "application/json",
        "response_schema": GroundedResponse,
        "temperature": 0.0,
    }
    config = types.GenerateContentConfig(**config_args) if types is not None else None

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return _parse_and_validate_gemini_output(response, query, bundle)


# ---------------------------------------------------------------------------
# Deterministic Grounded Fallback Assembly
# ---------------------------------------------------------------------------

def build_deterministic_fallback(
    query: str, bundle: EvidenceBundle
) -> GroundedResponse:
    """
    Assemble deterministic grounded response when Gemini is unavailable,
    times out, fails validation, or errors out.
    """
    extracted_error_code = bundle.extracted_error_code or extract_error_code(query)
    sections = []

    relevant_rag_doc: Optional[Dict[str, Any]] = None
    is_exact_error_match = False
    is_error_specific_doc = False

    if bundle.rag_docs:
        top_doc = bundle.rag_docs[0]
        doc_content = top_doc.get("content", "")
        doc_title = top_doc.get("title", "")
        doc_error_code = extract_error_code(doc_title + " " + doc_content)

        if extracted_error_code:
            if extracted_error_code.lower() in (doc_title + " " + doc_content).lower():
                relevant_rag_doc = top_doc
                is_exact_error_match = True
            else:
                relevant_rag_doc = None
        else:
            search_type = top_doc.get("search_type", "vector")
            score = top_doc.get("score", 0.0)
            if search_type == "vector" and score >= RAG_RELEVANCE_THRESHOLD:
                relevant_rag_doc = top_doc
            elif search_type == "text":
                relevant_rag_doc = top_doc if _doc_relevant_for_text_fallback(query, top_doc) else None
            else:
                relevant_rag_doc = None
            if doc_error_code:
                is_error_specific_doc = True

    # 📖 RAG Section
    if extracted_error_code:
        if relevant_rag_doc and is_exact_error_match:
            best_title = relevant_rag_doc.get("title", "Knowledge Guide")
            best_cat = relevant_rag_doc.get("category", "General")
            best_snip = get_clean_snippet(relevant_rag_doc.get("content", ""))
            doc_header = f"Retrieved from Knowledge Guide: **{best_title}** ({best_cat})"
            sections.append(f"📖 **Technical Documentation (RAG)**\n{doc_header}\n> {best_snip}")
        else:
            sections.append(
                f"📖 **Technical Documentation (RAG)**\n"
                f"No specific documentation match found for error code `{extracted_error_code}`."
            )
    else:
        if relevant_rag_doc:
            best_title = relevant_rag_doc.get("title", "Knowledge Guide")
            best_cat = relevant_rag_doc.get("category", "General")
            best_snip = get_clean_snippet(relevant_rag_doc.get("content", ""))
            if is_error_specific_doc:
                doc_header = f"Retrieved from Related Knowledge Guide (General Reference): **{best_title}** ({best_cat})"
            else:
                doc_header = f"Retrieved from Knowledge Guide: **{best_title}** ({best_cat})"
            sections.append(f"📖 **Technical Documentation (RAG)**\n{doc_header}\n> {best_snip}")
        else:
            sections.append("📖 **Technical Documentation (RAG)**\nNo specific documentation match found in knowledge base.")

    # 🎟️ SQL Section
    sql_ticket_res_str = bundle.sql_ticket_summary or "\n".join(bundle.tickets)
    sql_log_res_str = bundle.sql_log_summary or "\n".join(bundle.error_logs)
    has_sql = bool(bundle.sql_ticket_summary or bundle.sql_log_summary or bundle.tickets or bundle.error_logs)

    if has_sql:
        sql_summary = []
        if "No support tickets match" not in sql_ticket_res_str and sql_ticket_res_str:
            sql_summary.append(f"Matching Tickets:\n{sql_ticket_res_str}")
        if "No matching error logs" not in sql_log_res_str and sql_log_res_str:
            sql_summary.append(f"System Logs:\n{sql_log_res_str}")

        if sql_summary:
            sections.append("🎟️ **Historical Ticket & Log Context (SQL)**\n" + "\n".join(sql_summary))
        else:
            if extracted_error_code:
                sections.append(
                    f"🎟️ **Historical Ticket & Log Context (SQL)**\n"
                    f"No historical ticket or error-log match found for error code `{extracted_error_code}`."
                )
            else:
                sections.append("🎟️ **Historical Ticket & Log Context (SQL)**\nNo prior unresolved incidents recorded for this query.")
    else:
        sections.append("🎟️ **Historical Ticket & Log Context (SQL)**\nNot queried for this request.")

    # 💡 Troubleshooting Section
    troubleshooting_steps = []
    if extracted_error_code:
        if relevant_rag_doc and is_exact_error_match:
            troubleshooting_steps = extract_troubleshooting_steps(relevant_rag_doc.get("content", ""))
        if not troubleshooting_steps:
            troubleshooting_steps = [
                f"No grounded troubleshooting procedure was found for `{extracted_error_code}` in the knowledge base.",
                f"No historical ticket or error-log evidence was found for error code `{extracted_error_code}`.",
                "Collect the relevant VPN/system logs and escalate to IT support if the issue persists.",
            ]
    else:
        if relevant_rag_doc:
            steps = extract_troubleshooting_steps(relevant_rag_doc.get("content", ""))
            if steps:
                troubleshooting_steps = steps
        if not troubleshooting_steps:
            troubleshooting_steps = [NO_GROUNDED_PROCEDURE_MSG]

    sections.append(
        "💡 **Grounded Troubleshooting & Action Plan**\n"
        + "\n".join(troubleshooting_steps)
    )

    answer = "\n\n".join(sections)
    is_grounded = bool(relevant_rag_doc or (has_sql and sql_summary if 'sql_summary' in locals() else False))
    evidence_used = []
    if relevant_rag_doc:
        evidence_used.append(relevant_rag_doc.get("title", "Knowledge Guide"))

    return GroundedResponse(
        answer=answer,
        grounded=is_grounded,
        confidence=0.85 if is_grounded else 0.0,
        evidence_used=evidence_used,
    )


# ---------------------------------------------------------------------------
# Public Synthesis Interface
# ---------------------------------------------------------------------------

def generate_grounded_response(
    query: str,
    evidence: Union[EvidenceBundle, Dict[str, Any]],
    client: Optional[Any] = None,
    model_name: Optional[str] = None,
) -> GroundedResponse:
    """
    Generate a strictly grounded IT support response.

    1. If evidence bundle has no usable evidence, immediately returns conservative
       no-grounded-procedure response without calling Gemini.
    2. Attempts Gemini response synthesis with structured schema enforcement.
    3. On any failure (API key missing, network error, timeout, malformed JSON, invalid confidence,
       or grounding validation failure), safely falls back to deterministic grounded response.
    """
    if isinstance(evidence, dict):
        bundle = EvidenceBundle.model_validate(evidence)
    else:
        bundle = evidence

    # Rule 3: No-evidence behavior — do NOT call Gemini
    if not has_usable_evidence(bundle):
        return build_deterministic_fallback(query, bundle)

    # Attempt Gemini generation
    active_client = client or get_gemini_client()
    if active_client is not None:
        try:
            return _call_gemini_generation(
                client=active_client,
                query=query,
                bundle=bundle,
                model_name=model_name,
            )
        except Exception as exc:
            logger.warning(
                "Gemini response generation failed (%s); falling back to deterministic grounded assembly",
                type(exc).__name__,
            )

    # Rule 8: Fallback to deterministic grounded response assembly
    return build_deterministic_fallback(query, bundle)
