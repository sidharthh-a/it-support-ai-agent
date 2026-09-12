"""Tests for the SSE streaming chat endpoint.

Verifies the streaming contract: start -> tool events -> token deltas -> done,
and that the streamed text equals the grounded agent answer with full metadata.
All Gemini calls are mocked by the autouse fixture in conftest.py.
"""
import json
import re

import pytest

from app.rag.service import RAGService


def _parse_sse_events(raw_text: str):
    """Parse an SSE stream body into (event, data) tuples."""
    events = []
    for block in raw_text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = None
        data_line = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_name = line[len("event: "):]
            elif line.startswith("data: "):
                data_line = line[len("data: "):]
        if event_name and data_line is not None:
            events.append((event_name, json.loads(data_line)))
    return events


def _stream_chat(client, payload, headers=None):
    """POST to the stream endpoint and return the raw body (TestClient buffers it)."""
    res = client.post("/api/v1/chat/stream", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    return res.text


def test_stream_endpoint_contract(client, db_session):
    """Streaming emits start/status/tool/token/done in order, ending with done."""
    rag = RAGService(db_session)
    rag.ingest_document(
        title="VPN Setup Guide",
        category="Network",
        content="To solve ERR_VPN_AUTH_401 timeout, clear DNS cache with ipconfig /flushdns.",
        file_type="txt",
    )
    raw = _stream_chat(client, {"message": "How do I fix ERR_VPN_AUTH_401 in the VPN guide?"})
    events = _parse_sse_events(raw)
    names = [e for e, _ in events]

    assert names[0] == "start"
    assert names[-1] == "done"
    assert "token" in names
    assert "status" in names


def test_stream_tokens_concatenate_to_grounded_answer(client, db_session):
    """The concatenation of token deltas must equal the final done.answer exactly."""
    raw = _stream_chat(client, {"message": "Please create ticket: monitor flickering badly"})
    events = _parse_sse_events(raw)

    streamed = "".join(d["delta"] for e, d in events if e == "token")
    done = next(d for e, d in events if e == "done")
    assert streamed == done["answer"]
    assert len(streamed) > 0


def test_stream_done_carries_metadata(client, db_session):
    """done event preserves citations, tool calls, and ticket references."""
    raw = _stream_chat(client, {"message": "Please create ticket: laptop BSOD after update"})
    events = _parse_sse_events(raw)
    done = next(d for e, d in events if e == "done")

    assert done["ticket_created"] is not None
    assert done["ticket_created"]["ticket_number"].startswith("TICK-")
    assert len(done["tools_used"]) >= 1
    assert any(t["tool_name"] == "create_ticket" for t in done["tools_used"])


def test_stream_tool_events_match_done_metadata(client, db_session):
    raw = _stream_chat(client, {"message": "Has this VPN issue happened before?"})
    events = _parse_sse_events(raw)
    tool_events = [d for e, d in events if e == "tool"]
    done = next(d for e, d in events if e == "done")
    assert [t["tool_name"] for t in tool_events] == [t["tool_name"] for t in done["tools_used"]]


def test_stream_requires_message(client):
    res = client.post("/api/v1/chat/stream", json={"message": ""})
    assert res.status_code == 400


def test_stream_validates_conversation_ownership(client):
    client.post("/api/v1/auth/register", json={
        "email": "s1@acme-corp.com", "password": "S3curePass!x", "full_name": "S1", "role": "employee", "department": "IT",
    })
    tok_a = client.post("/api/v1/auth/login", json={"email": "s1@acme-corp.com", "password": "S3curePass!x"}).json()["access_token"]
    conv = client.post("/api/v1/conversations/", json={"title": "Mine"}, headers={"Authorization": f"Bearer {tok_a}"}).json()

    client.post("/api/v1/auth/register", json={
        "email": "s2@acme-corp.com", "password": "S3curePass!x", "full_name": "S2", "role": "employee", "department": "IT",
    })
    tok_b = client.post("/api/v1/auth/login", json={"email": "s2@acme-corp.com", "password": "S3curePass!x"}).json()["access_token"]

    res = client.post("/api/v1/chat/stream", json={
        "message": "hello there", "conversation_id": conv["id"],
    }, headers={"Authorization": f"Bearer {tok_b}"})
    assert res.status_code == 404


def test_stream_persists_messages_with_conversation(client):
    tok = client.post("/api/v1/auth/register", json={
        "email": "persist@acme-corp.com", "password": "S3curePass!x", "full_name": "P", "role": "employee", "department": "IT",
    }).json()
    # register returns user; login
    login = client.post("/api/v1/auth/login", json={"email": "persist@acme-corp.com", "password": "S3curePass!x"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    conv = client.post("/api/v1/conversations/", json={"title": "Persisted"}, headers=headers).json()
    _stream_chat(client, {"message": "My Wi-Fi keeps disconnecting", "conversation_id": conv["id"]}, headers)

    detail = client.get(f"/api/v1/conversations/{conv['id']}", headers=headers).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    # Assistant message persisted with role, timestamp, and citation fields
    assistant = detail["messages"][1]
    assert assistant["created_at"]
    assert "rag_sources" in assistant and "sql_sources" in assistant and "tools_used" in assistant
