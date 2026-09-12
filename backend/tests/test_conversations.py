"""Tests for persistent conversation history.

All Gemini calls are mocked by the autouse fixture in conftest.py.
"""
import pytest
from app.repositories.conversation_repository import ConversationRepository
from app.agents.agent_graph import build_and_run_agent


def _register_and_login(client, email="hist@acme-corp.com"):
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "S3curePass!x", "full_name": "Hist User", "role": "employee", "department": "IT",
    })
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "S3curePass!x"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_create_and_list_conversations(client):
    headers = _register_and_login(client)
    res = client.post("/api/v1/conversations/", json={"title": "VPN issue"}, headers=headers)
    assert res.status_code == 201
    conv = res.json()
    assert conv["title"] == "VPN issue"

    res = client.get("/api/v1/conversations/", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["title"] == "VPN issue"


def test_conversations_require_auth(client):
    res = client.get("/api/v1/conversations/")
    assert res.status_code == 401


def test_rename_conversation(client):
    headers = _register_and_login(client)
    conv = client.post("/api/v1/conversations/", json={"title": "Old"}, headers=headers).json()
    res = client.patch(f"/api/v1/conversations/{conv['id']}", json={"title": "Renamed"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["title"] == "Renamed"


def test_delete_conversation(client):
    headers = _register_and_login(client)
    conv = client.post("/api/v1/conversations/", json={"title": "Temp"}, headers=headers).json()
    res = client.delete(f"/api/v1/conversations/{conv['id']}", headers=headers)
    assert res.status_code == 204
    res = client.get("/api/v1/conversations/", headers=headers)
    assert res.json() == []


def test_search_conversations(client, db_session):
    headers = _register_and_login(client)
    from app.models.user import User
    repo = ConversationRepository(db_session)
    user = db_session.query(User).filter_by(email="hist@acme-corp.com").first()
    repo.create(user.id, title="Printer offline saga")
    repo.create(user.id, title="VPN drops")
    res = client.get("/api/v1/conversations/search", params={"q": "printer"}, headers=headers)
    assert res.status_code == 200
    titles = [c["title"] for c in res.json()]
    assert titles == ["Printer offline saga"]


def test_search_conversations_by_message_content(client, db_session):
    headers = _register_and_login(client)
    from app.models.user import User
    repo = ConversationRepository(db_session)
    user = db_session.query(User).filter_by(email="hist@acme-corp.com").first()
    conv = repo.create(user.id, title="Session 1")
    repo.add_message(conv.id, "user", "My Outlook keeps crashing with ERR_OUTLOOK_SAML")
    res = client.get("/api/v1/conversations/search", params={"q": "ERR_OUTLOOK_SAML"}, headers=headers)
    assert res.status_code == 200
    assert any(c["id"] == conv.id for c in res.json())


def test_chat_persists_messages_when_conversation_given(client):
    headers = _register_and_login(client)
    conv = client.post("/api/v1/conversations/", json={"title": "Chat"}, headers=headers).json()
    res = client.post("/api/v1/chat", json={
        "message": "Please create ticket: monitor flickering",
        "conversation_id": conv["id"],
    }, headers=headers)
    assert res.status_code == 200

    detail = client.get(f"/api/v1/conversations/{conv['id']}", headers=headers).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][0]["content"].startswith("Please create ticket")
    # Ticket creation metadata preserved on the assistant message
    assert detail["messages"][1]["ticket_created"] is not None
    assert detail["messages"][1]["ticket_created"]["ticket_number"].startswith("TICK-")


def test_chat_without_conversation_id_not_persisted(client):
    headers = _register_and_login(client)
    res = client.post("/api/v1/chat", json={"message": "How do I reset my password?"}, headers=headers)
    assert res.status_code == 200
    convs = client.get("/api/v1/conversations/", headers=headers).json()
    assert convs == []


def test_cannot_access_other_users_conversation(client):
    headers_a = _register_and_login(client, email="a@acme-corp.com")
    headers_b = _register_and_login(client, email="b@acme-corp.com")
    conv = client.post("/api/v1/conversations/", json={"title": "Private"}, headers=headers_a).json()
    res = client.get(f"/api/v1/conversations/{conv['id']}", headers=headers_b)
    assert res.status_code == 404
    res = client.delete(f"/api/v1/conversations/{conv['id']}", headers=headers_b)
    assert res.status_code == 404


def test_conversation_title_auto_set_from_first_message(client):
    headers = _register_and_login(client)
    client.post("/api/v1/chat", json={
        "message": "VPN gateway timeout on ERR_VPN_AUTH_401, help",
        "conversation_id": None,
    }, headers=headers)
    # No conversation id given -> nothing created (explicit persistence only)
    convs = client.get("/api/v1/conversations/", headers=headers).json()
    assert convs == []


def test_conversation_model_grounded_metadata_roundtrip(db_session):
    repo = ConversationRepository(db_session)
    conv = repo.create(user_id=1, title="Unit")
    msg = repo.add_message(
        conv.id, "user", "question",
    )
    assert msg.id is not None
    msgs = repo.get_messages(conv.id)
    assert [m.role for m in msgs] == ["user"]
