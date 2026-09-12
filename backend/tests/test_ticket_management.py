"""Tests for extended ticket management: comments, related logs, RBAC, escalate."""
import pytest
from app.repositories.ticket_repository import TicketRepository
from app.repositories.error_log_repository import ErrorLogRepository
from app.schemas.ticket import TicketCreate, TicketUpdate
from app.schemas.error_log import ErrorLogCreate


def _make_ticket(db_session, title="VPN flapping", **kwargs):
    repo = TicketRepository(db_session)
    return repo.create_ticket(TicketCreate(title=title, description="Gateway timeouts", priority="high", category="network", user_id=1, **kwargs))


def _register_and_login(client, email, password="S3curePass!x", role="employee"):
    client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": "T", "role": role, "department": "IT",
    })
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_add_and_list_comments(client, db_session):
    ticket = _make_ticket(db_session)
    res = client.post(f"/api/v1/tickets/{ticket.id}/comments", json={"body": "Investigating now"})
    assert res.status_code == 201
    res = client.get(f"/api/v1/tickets/{ticket.id}/comments")
    assert res.status_code == 200
    comments = res.json()
    assert len(comments) == 1
    assert comments[0]["body"] == "Investigating now"


def test_comment_on_missing_ticket_404(client):
    res = client.post("/api/v1/tickets/999999/comments", json={"body": "hi"})
    assert res.status_code == 404


def test_comment_requires_nonempty_body(client, db_session):
    ticket = _make_ticket(db_session)
    res = client.post(f"/api/v1/tickets/{ticket.id}/comments", json={"body": ""})
    assert res.status_code == 422


def test_related_logs_endpoint(client, db_session):
    ticket = _make_ticket(db_session)
    log_repo = ErrorLogRepository(db_session)
    log_repo.create(ErrorLogCreate(
        service_name="vpn-gateway", error_code="ERR_VPN_AUTH_401",
        log_message="Handshake failed", ticket_id=ticket.id,
    ))
    res = client.get(f"/api/v1/tickets/{ticket.id}/logs")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) == 1
    assert logs[0]["error_code"] == "ERR_VPN_AUTH_401"


def test_related_logs_empty(client, db_session):
    ticket = _make_ticket(db_session)
    res = client.get(f"/api/v1/tickets/{ticket.id}/logs")
    assert res.status_code == 200
    assert res.json() == []


def test_employee_sees_only_own_tickets(client, db_session):
    _make_ticket(db_session, title="Admin ticket A")
    own = _make_ticket(db_session, title="Mine only B")
    headers = _register_and_login(client, "emp@acme-corp.com")
    # Registered user id=2 sees only their own (none created by them)
    res = client.get("/api/v1/tickets/", headers=headers)
    assert res.status_code == 200
    assert all(t["user_id"] != 1 for t in res.json())


def test_admin_sees_all_tickets(client, db_session):
    _make_ticket(db_session, title="Admin sees this")
    headers = _register_and_login(client, "test.user@acme-corp.com", password="testadmin123")
    res = client.get("/api/v1/tickets/", headers=headers)
    assert res.status_code == 200
    titles = [t["title"] for t in res.json()]
    assert any("Admin sees this" in t for t in titles)


def test_assigned_to_filter(client, db_session):
    from app.models.user import User
    tech = User(email="tech.assign@acme-corp.com", full_name="Tech", role="support", department="IT")
    db_session.add(tech)
    db_session.commit()
    db_session.refresh(tech)

    _make_ticket(db_session, title="Assigned ticket")
    repo = TicketRepository(db_session)
    repo.update_ticket(1, TicketUpdate(assigned_to_id=tech.id))

    res = client.get("/api/v1/tickets/", params={"assigned_to_id": tech.id})
    assert res.status_code == 200
    assert all(t["assigned_to_id"] == tech.id for t in res.json())


def test_escalate_endpoint(client, db_session):
    ticket = _make_ticket(db_session, title="Need escalation")
    headers = _register_and_login(client, "test.user@acme-corp.com", password="testadmin123")
    res = client.post(f"/api/v1/tickets/{ticket.id}/escalate", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "escalated"
    assert data["priority"] == "critical"
    # Audit history recorded
    hist = client.get(f"/api/v1/tickets/{ticket.id}/history").json()
    fields = {h["field_changed"] for h in hist}
    assert "status" in fields


def test_escalate_denied_for_anonymous_without_staff(client, db_session):
    ticket = _make_ticket(db_session, title="Anon escalate try")
    res = client.post(f"/api/v1/tickets/{ticket.id}/escalate")
    assert res.status_code == 403
