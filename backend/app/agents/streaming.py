"""SSE streaming support for the grounded IT-support agent.

Streaming contract (Server-Sent Events, one JSON object per `data:` line):

  event: start   -> {"conversation_id": int|None}
  event: status  -> {"stage": "routing"|"retrieving"|"synthesizing"}
  event: tool    -> {"tool_name": str, "arguments": {...}, "result_summary": str}
  event: ticket  -> {...ticket_created info...}
  event: token   -> {"delta": str}
  event: done    -> {"answer": str, "grounded": bool, "confidence": float,
                     "evidence_used": [...], "tools_used": [...],
                     "rag_sources": [...], "sql_sources": [...],
                     "ticket_created": {...}|None, "ticket_updated": {...}|None}
  event: error   -> {"detail": str}

Grounding guarantee: the *text* streamed token-by-token is exactly the
deterministic/grounded answer produced by the existing agent pipeline —
the final `done` event carries the same full metadata the non-streaming
endpoint returns, so citations can never drift from the streamed answer.
"""
import asyncio
import json
from typing import AsyncGenerator, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agents.agent_graph import build_and_run_agent
from app.core.logging import logger
from app.schemas.chat import ChatMessage

# Split the grounded answer into small token-ish chunks so the client renders
# a smooth typing animation. We split on word boundaries and re-attach spaces.
_TOKEN_CHUNK_WORDS = 2


def _tokenize_answer(answer: str) -> List[str]:
    """Split grounded answer into small chunks for streaming."""
    if not answer:
        return []
    chunks: List[str] = []
    words = answer.split(" ")
    for i in range(0, len(words), _TOKEN_CHUNK_WORDS):
        group = words[i:i + _TOKEN_CHUNK_WORDS]
        piece = " ".join(group)
        if i + _TOKEN_CHUNK_WORDS < len(words):
            piece += " "
        chunks.append(piece)
    return chunks


def _sse(event: str, data: Dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def run_agent_stream(
    db: Session,
    user_message: str,
    history: Optional[List[ChatMessage]] = None,
    gemini_client=None,
    gemini_model: Optional[str] = None,
    conversation_id: Optional[int] = None,
    token_delay_seconds: float = 0.015,
) -> AsyncGenerator[str, None]:
    """Async generator producing the SSE event stream for one chat turn.

    Runs the synchronous grounded agent pipeline once (via to_thread so the
    event loop is never blocked), then streams the resulting grounded answer
    token-by-token followed by the full metadata `done` event.
    """

    async def _generate() -> AsyncGenerator[str, None]:
        yield _sse("start", {"conversation_id": conversation_id})

        yield _sse("status", {"stage": "routing"})

        # Run the deterministic grounded pipeline in a worker thread.
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: build_and_run_agent(
                    db=db,
                    user_message=user_message,
                    history=history or [],
                    gemini_client=gemini_client,
                    gemini_model=gemini_model,
                ),
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Streaming agent failed: %s", type(exc).__name__)
            yield _sse("error", {"detail": f"Agent execution failed: {type(exc).__name__}"})
            return

        # Replay tool executions as they were recorded by the pipeline.
        for tool_call in response.tools_used:
            yield _sse("tool", {
                "tool_name": tool_call.tool_name,
                "arguments": tool_call.arguments,
                "result_summary": tool_call.result_summary,
            })

        if response.ticket_created:
            yield _sse("ticket", response.ticket_created)
        if response.ticket_updated:
            yield _sse("ticket", response.ticket_updated)

        yield _sse("status", {"stage": "synthesizing"})

        # Stream the grounded answer token-by-token.
        for piece in _tokenize_answer(response.answer):
            yield _sse("token", {"delta": piece})
            if token_delay_seconds > 0:
                await asyncio.sleep(token_delay_seconds)

        yield _sse("done", {
            "answer": response.answer,
            "grounded": getattr(response, "grounded", None),
            "confidence": getattr(response, "confidence", None),
            "evidence_used": getattr(response, "evidence_used", []) or [],
            "tools_used": [t.model_dump() for t in response.tools_used],
            "rag_sources": response.rag_sources,
            "sql_sources": response.sql_sources,
            "ticket_created": response.ticket_created,
            "ticket_updated": response.ticket_updated,
        })

    return _generate()
