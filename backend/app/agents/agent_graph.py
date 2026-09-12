import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.agents.state import AgentState
from app.tools.agent_tools import create_agent_tools, extract_error_code
from app.schemas.chat import ChatMessage, ChatResponse, ToolCallDetail
from app.repositories.ticket_repository import TicketRepository
from app.repositories.error_log_repository import ErrorLogRepository
from app.rag.service import RAGService
from app.agents.intent_router import route_query, QueryIntent
from app.agents.response_generator import (
    generate_grounded_response,
    EvidenceBundle,
    GroundedResponse,
)


# Minimum cosine-similarity score for a RAG result to be considered relevant.
# Vector-fallback text results return 0.0; meaningful domain matches typically
# score well above this value. Tune via settings if needed.
RAG_RELEVANCE_THRESHOLD = 0.35


def get_clean_snippet(text: str, max_chars: int = 350) -> str:
    """Extract a clean snippet without cutting mid-word or mid-sentence.

    When the cut point lands mid-sentence, the function extends forward to
    complete that sentence (up to max_chars + 200 chars) so that numbered
    steps are never shown as dangling headers (e.g. '4.').  List-marker dots
    (digits followed by '. ') are skipped when looking for a sentence boundary.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text

    # Helper: is position `pos` a real sentence-ending dot (not a list marker)?
    def _is_sentence_dot(s: str, pos: int) -> bool:
        """True when s[pos] == '.' and the char before it is not a digit."""
        return pos >= 0 and s[pos] == "." and (pos == 0 or not s[pos - 1].isdigit())

    # --- Try to extend forward: find the next sentence end after max_chars ---
    # Search window: up to 200 chars past max_chars
    search_end = min(len(text), max_chars + 200)
    forward_end = -1
    for i in range(max_chars - 1, search_end):
        if i >= len(text):
            break
        if text[i] == "." and _is_sentence_dot(text, i):
            # Accept if followed by space, newline, or end-of-string
            after = text[i + 1] if i + 1 < len(text) else ""
            if after in ("", " ", "\n"):
                forward_end = i
                break

    if forward_end > 0:
        return text[:forward_end + 1].strip()

    # --- Fallback: walk backward from max_chars to last sentence boundary ---
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
            pos -= 1  # list-marker dot; keep searching leftward

    if best_dot > 100:
        return truncated[:best_dot + 1].strip()

    last_space = truncated.rfind(" ")
    if last_space > 100:
        return truncated[:last_space].strip() + "..."
    return truncated.strip()


def extract_troubleshooting_steps(content: str) -> List[str]:
    """Extract complete numbered or bulleted troubleshooting steps from document content."""
    steps = []
    raw_blocks = re.findall(r"(?:^|\n)\s*(\d+[\.\)]\s+.*?)(?=\n\s*\d+[\.\)]|\n\n|$)", content, re.DOTALL)
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


_GREETING_TOKENS = {
    "hey", "hi", "hello", "howdy", "hiya", "yo", "sup", "greetings",
    "good morning", "good afternoon", "good evening", "good day",
    "what's up", "whats up", "how are you", "how r u",
    "thanks", "thank you", "thx", "cheers", "bye", "goodbye", "see you",
    "help", "can you help", "are you there",
}

# Technical signals used only by the greeting guard (keeps existing behaviour).
_TECHNICAL_SIGNALS = {
    "error", "err_", "disconnect", "fail", "issue", "problem", "vpn",
    "wifi", "network", "password", "login", "install", "crash", "slow",
    "fix", "setup", "reset", "ticket", "log",
}

# ---------------------------------------------------------------------------
# Domain classifier signal sets
# ---------------------------------------------------------------------------
# Strong positive IT-support signals.  Any match → query is IT-domain.
# These terms are unambiguous: they never appear in general CS questions.
_IT_POSITIVE_SIGNALS = {
    # Error-code prefix handled separately via regex
    # Network / infrastructure
    "vpn", "wi-fi", "wifi", "network", "dns", "gateway", "firewall",
    "proxy", "dhcp", "ssl", "tls", "certificate", "cert",
    "ldap", "802.1x", "ethernet", "bandwidth", "latency",
    # Device / hardware
    "laptop", "workstation", "printer", "monitor", "screen", "keyboard",
    "mouse", "usb", "docking", "headset", "webcam",
    # IT-domain identity / access
    "login", "password", "credential", "authenticate", "authentication",
    "sso", "okta", "saml", "oauth", "mfa", "2fa", "active directory",
    "bitlocker", "intune", "endpoint",
    # Collaboration / productivity apps (IT-managed)
    "outlook", "teams", "sharepoint", "onedrive", "zoom",
    "globalprotect", "palo alto",
    # IT ops nouns / verbs
    "ticket", "helpdesk", "escalate", "reboot", "reinstall",
    "patch", "driver", "firmware", "vpn client",
}

# Strong general / programming signals.
# Only checked when NO IT-positive signal is found.
# These terms are unambiguous: they never appear in IT support queries.
_GENERAL_SIGNALS = {
    # Programming languages (standalone words)
    "python", "javascript", "typescript", "java", "c++", "c#", "rust",
    "golang", "ruby", "php", "kotlin", "swift", "scala", "haskell",
    "r language", "matlab",
    # CS / algorithms
    "algorithm", "recursion", "recursive", "binary tree", "binary search",
    "linked list", "sorting", "sort algorithm", "merge sort", "quicksort",
    "bubble sort", "hash map", "hash table", "graph traversal",
    "depth first", "breadth first", "dynamic programming", "memoization",
    "big o", "time complexity", "space complexity",
    # Programming constructs (only when no IT context)
    "function to", "write a function", "implement a", "code to",
    "reverse a list", "reverse a string", "reverse an array",
    "fibonacci", "factorial", "prime number", "palindrome",
    "matrix multiplication", "data structure",
    # General knowledge
    "what is a", "define ", "meaning of", "explain the concept",
}


def classify_query_domain(message: str) -> str:
    """
    Deterministic domain classifier — no LLM call.

    Returns one of:
      "it_support"  – query is about IT infrastructure, devices, or access.
      "general"     – query is about general knowledge or programming.
      "ambiguous"   – cannot determine with confidence; treat conservatively
                      as "it_support" at the call site.

    Algorithm:
      1. Error-code pattern (ERR_* / ERROR_*) → always IT support.
      2. Any IT-positive signal word/phrase in message → it_support.
      3. Any general-negative signal in message (and no IT signal) → general.
      4. Fallback → ambiguous.
    """
    msg = message.strip().lower()

    # Step 1: explicit error code → always IT support
    if re.search(r"\berr(?:or)?_[a-z0-9_]+\b", msg):
        return "it_support"

    # Step 2: IT-positive signals
    for signal in _IT_POSITIVE_SIGNALS:
        if signal in msg:
            return "it_support"

    # Step 3: general / programming signals (no IT signal found above)
    for signal in _GENERAL_SIGNALS:
        if signal in msg:
            return "general"

    # Step 4: ambiguous — caller should treat conservatively as it_support
    return "ambiguous"


def is_greeting_or_casual_query(message: str) -> bool:
    """
    Returns True when the message is a greeting or purely casual query that
    requires no tool use.  Uses deterministic token matching — no LLM call.
    """
    msg = message.strip().lower()
    # Strip trailing punctuation for single-token check
    bare = msg.rstrip("!.,?")

    # If any technical signal appears, treat as a real IT query
    for signal in _TECHNICAL_SIGNALS:
        if signal in msg:
            return False

    # Short message: check against known greeting tokens.
    # Also try a punctuation-stripped variant so "Hello!" / "How are you?" match.
    if len(msg.split()) <= 6:
        candidates = {msg, bare}
        # Collapse every non-word char to a single space: "how are you?" -> "how are you"
        collapsed = re.sub(r"[^a-z0-9\s]", " ", msg)
        candidates.add(collapsed.strip())
        candidates.add(collapsed.strip() + " ")
        for token in _GREETING_TOKENS:
            if any(
                c == token or c.startswith(token + " ") or c.endswith(" " + token) or c == token + " "
                for c in candidates
            ):
                return True

    return False


def build_and_run_agent(
    db: Session,
    user_message: str,
    history: List[ChatMessage] = None,
    gemini_client: Optional[Any] = None,
    gemini_model: Optional[str] = None,
) -> ChatResponse:
    """
    Deterministic grounded dual-retrieval agent with Gemini response synthesis.

    All retrieval calls are performed in a controlled manner.
    The retrieved evidence bundle is passed to the grounded response generator.
    """
    # ------------------------------------------------------------------ #
    # Intent Routing (Safety overrides -> Gemini router -> Fallback)     #
    # ------------------------------------------------------------------ #
    intent_result = route_query(user_message, client=gemini_client, model_name=gemini_model)

    if intent_result.intent == QueryIntent.CASUAL:
        return ChatResponse(
            answer="Hey! How can I help you with an IT issue?",
            tools_used=[],
            ticket_created=None,
            ticket_updated=None,
            rag_sources=[],
            sql_sources=[]
        )

    if intent_result.intent == QueryIntent.GENERAL:
        # General / programming query — answer directly without any tools.
        return ChatResponse(
            answer=(
                "I'm an IT support assistant, so I may not be the best source "
                "for general programming or knowledge questions. That said, "
                "feel free to ask me any IT-related issues — VPN, Wi-Fi, "
                "passwords, software, hardware, and more!"
            ),
            tools_used=[],
            ticket_created=None,
            ticket_updated=None,
            rag_sources=[],
            sql_sources=[]
        )

    if intent_result.intent == QueryIntent.AMBIGUOUS:
        # Ambiguous query — prompt user for specific IT issue details without tool execution.
        return ChatResponse(
            answer=(
                "I'm here to help with IT support! Could you please provide more details "
                "or describe the specific issue you're experiencing (e.g., error messages, "
                "affected device, application, VPN, or network problems)?"
            ),
            tools_used=[],
            ticket_created=None,
            ticket_updated=None,
            rag_sources=[],
            sql_sources=[]
        )

    # intent == QueryIntent.IT_SUPPORT: proceed with specialized IT support retrieval

    tools = create_agent_tools(db)
    tool_map = {t.name: t for t in tools}

    tools_used_list: List[ToolCallDetail] = []
    ticket_created_info: Optional[Dict[str, Any]] = None
    ticket_updated_info: Optional[Dict[str, Any]] = None
    rag_sources: List[Dict[str, Any]] = []
    sql_sources: List[Dict[str, Any]] = []

    rag_service = RAGService(db)
    query_lower = user_message.lower()

    # ------------------------------------------------------------------ #
    # Intent 1: Explicit Ticket Creation                                  #
    # ------------------------------------------------------------------ #
    if "create ticket" in query_lower or "open ticket" in query_lower or "submit ticket" in query_lower:
        tool_res = tool_map["create_ticket"].invoke({
            "title": f"User Issue: {user_message[:50]}",
            "description": user_message,
            "priority": "high" if ("urgent" in query_lower or "critical" in query_lower) else "medium",
            "category": "network" if "vpn" in query_lower or "wifi" in query_lower else "software"
        })
        tools_used_list.append(ToolCallDetail(tool_name="create_ticket", arguments={"title": user_message[:50]}, result_summary=tool_res))
        try:
            ticket_created_info = json.loads(tool_res)
        except Exception:
            pass
        t_info = ticket_created_info or {}
        answer = (
            f"I have created a support ticket for your issue:\n\n"
            f"**{t_info.get('message', 'Ticket Created')}**\n"
            f"- **Ticket Number:** {t_info.get('ticket_number')}\n"
            f"- **Priority:** {t_info.get('priority')}\n"
            f"- **Status:** Open\n\n"
            f"An IT technician has been assigned to investigate."
        )
        return ChatResponse(
            answer=answer,
            tools_used=tools_used_list,
            ticket_created=ticket_created_info,
            ticket_updated=ticket_updated_info,
            rag_sources=rag_sources,
            sql_sources=sql_sources
        )

    # ------------------------------------------------------------------ #
    # Intent Detection                                                    #
    # ------------------------------------------------------------------ #
    has_rag_intent = any(k in query_lower for k in ["how", "fix", "guide", "setup", "solve", "disconnect", "error", "timeout", "reset", "check"])
    has_sql_intent = any(k in query_lower for k in ["happen", "before", "history", "ticket", "log", "previous", "status", "again"])

    # Default: both RAG + SQL for comprehensive grounded answers
    if not has_rag_intent and not has_sql_intent:
        has_rag_intent = True
        has_sql_intent = True

    extracted_error_code = extract_error_code(user_message)

    # ------------------------------------------------------------------ #
    # Determine retrieval arguments before spawning threads               #
    # ------------------------------------------------------------------ #
    sql_ticket_args: Optional[Dict[str, Any]] = None
    sql_log_args: Optional[Dict[str, Any]] = None
    do_rag = has_rag_intent

    if extracted_error_code:
        sql_ticket_args = {"query": extracted_error_code}
        sql_log_args = {"error_code": extracted_error_code}
    elif has_sql_intent or "vpn" in query_lower or "wifi" in query_lower or "error" in query_lower:
        sql_ticket_args = {"query": user_message}
        if "error" in query_lower or "disconnect" in query_lower or "log" in query_lower or "fail" in query_lower:
            sql_log_args = {"query": user_message}

    # ------------------------------------------------------------------ #
    # Thread-Safe Sequential Retrieval                                    #
    # ------------------------------------------------------------------ #
    sql_ticket_res_str = ""
    sql_log_res_str = ""
    rag_docs = []

    if sql_ticket_args is not None:
        try:
            sql_ticket_res_str = tool_map["search_tickets"].invoke(sql_ticket_args)
        except Exception as e:
            logger.warning(f"search_tickets failed: {e}")
            sql_ticket_res_str = "No support tickets match the given criteria."

    if sql_log_args is not None:
        try:
            sql_log_res_str = tool_map["search_error_logs"].invoke(sql_log_args)
        except Exception as e:
            logger.warning(f"search_error_logs failed: {e}")
            sql_log_res_str = "No matching error logs found."

    if do_rag:
        try:
            rag_docs = rag_service.search_knowledge(user_message, 3)
        except Exception as e:
            logger.warning(f"search_knowledge failed: {e}")
            rag_docs = []

    # ------------------------------------------------------------------ #
    # Record tool usage for audit / UI                                    #
    # ------------------------------------------------------------------ #
    if sql_ticket_args is not None:
        tools_used_list.append(ToolCallDetail(
            tool_name="search_tickets",
            arguments=sql_ticket_args,
            result_summary=sql_ticket_res_str[:200]
        ))
        sql_sources.append({"tool": "search_tickets", "result": sql_ticket_res_str})

    if sql_log_args is not None:
        tools_used_list.append(ToolCallDetail(
            tool_name="search_error_logs",
            arguments=sql_log_args,
            result_summary=sql_log_res_str[:200]
        ))
        sql_sources.append({"tool": "search_error_logs", "result": sql_log_res_str})

    if rag_docs:
        doc_summary_parts = []
        for d in rag_docs:
            title = d.get("title", "Unknown Document")
            content = d.get("content", "")
            if "title" not in d or "content" not in d:
                logger.warning(f"RAG result missing expected fields: {list(d.keys())}")
            doc_summary_parts.append(f"- {title}: {content[:150]}")
        doc_summary = "\n".join(doc_summary_parts)
        tools_used_list.append(ToolCallDetail(
            tool_name="search_documents",
            arguments={"query": user_message},
            result_summary=doc_summary[:200]
        ))
        for d in rag_docs:
            rag_sources.append({
                "title": d.get("title", "Unknown Document"),
                "category": d.get("category", "General"),
                "snippet": get_clean_snippet(d.get("content", "")),
                "content": d.get("content", ""),
                "score": d.get("score", 0.95),
                # search_type: "vector" (pgvector cosine) or "text" (keyword fallback).
                # Passed through so the relevance gate can treat them differently.
                "search_type": d.get("search_type", "vector"),
            })

    # ------------------------------------------------------------------ #
    # Auto-escalation for critical/urgent queries                         #
    # ------------------------------------------------------------------ #
    auto_escalated = False
    if "urgent" in query_lower or "critical" in query_lower or "outage" in query_lower:
        tool_res = tool_map["create_ticket"].invoke({
            "title": f"Escalated Issue: {user_message[:50]}",
            "description": user_message,
            "priority": "critical",
            "category": "network"
        })
        tools_used_list.append(ToolCallDetail(
            tool_name="create_ticket",
            arguments={"title": user_message[:50]},
            result_summary=tool_res
        ))
        try:
            ticket_created_info = json.loads(tool_res)
        except Exception:
            pass
        auto_escalated = True

    # ------------------------------------------------------------------ #
    # Grounded Response Synthesis via Evidence Bundle & Gemini Generator  #
    # ------------------------------------------------------------------ #
    evidence_bundle = EvidenceBundle(
        query=user_message,
        extracted_error_code=extracted_error_code,
        rag_docs=rag_sources,
        sql_ticket_summary=sql_ticket_res_str,
        sql_log_summary=sql_log_res_str,
        tool_results=[{"tool": t.tool_name, "summary": t.result_summary} for t in tools_used_list],
        auto_escalated=auto_escalated,
        ticket_created_info=ticket_created_info,
    )

    grounded_res = generate_grounded_response(
        query=user_message,
        evidence=evidence_bundle,
        client=gemini_client,
        model_name=gemini_model,
    )

    answer = grounded_res.answer

    if auto_escalated and ticket_created_info:
        escalation_note = (
            f"⚠️ **Escalation Note:** Due to high priority, "
            f"Ticket #{ticket_created_info.get('ticket_number')} "
            f"was automatically opened for IT Operations."
        )
        if escalation_note not in answer and f"#{ticket_created_info.get('ticket_number')}" not in answer:
            answer = f"{answer}\n\n{escalation_note}"

    return ChatResponse(
        answer=answer,
        tools_used=tools_used_list,
        ticket_created=ticket_created_info,
        ticket_updated=ticket_updated_info,
        rag_sources=rag_sources,
        sql_sources=sql_sources,
    )

