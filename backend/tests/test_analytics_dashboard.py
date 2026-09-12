"""Tests for the analytics dashboard endpoint — all values must be SQL-computed."""
import pytest
from datetime import datetime, timezone, timedelta

from app.repositories.ticket_repository import TicketRepository
from app.schemas.ticket import TicketCreate
from app.models.resolution import Resolution
from app.models.error_log import ErrorLog
from app.schemas.error_log import ErrorLogCreate


def _seed(db_session):
    repo = TicketRepository(db_session)
    now = datetime.now(timezone.utc)
    t1 = repo.create_ticket(TicketCreate(title="VPN down", description="x", priority="high", category="network", user_id=1))
    t2 = repo.create_ticket(title := TicketCreate(title="Outlook crash", description="y", priority="low", category="software", user_id=1))
    repo.update_ticket(t1.id, __import__("app.schemas.ticket", fromlist=["TicketUpdate"]).TicketUpdate(status="resolved"))
    # Resolution with a known duration (created_at -> resolved_at)
    res = Resolution(
        ticket_id=t1.id,
        solution_summary="Fixed",
        steps_taken="1. Did things.",
        resolved_by_id=1,
        resolved_at=now + timedelta(hours=3),
    )
    db_session.add(res)
    db_session.add(ErrorLog(service_name="vpn", error_code="ERR_VPN_AUTH_401", log_message="fail"))
    db_session.add(ErrorLog(service_name="vpn", error_code="ERR_VPN_AUTH_401", log_message="fail again"))
    db_session.add(ErrorLog(service_name="mail", error_code="ERR_OUTLOOK_SAML", log_message="saml fail"))
    db_session.commit()
    return t1, t2


def test_dashboard_endpoint_shape(client, db_session):
    _seed(db_session)
    res = client.get("/api/v1/analytics/dashboard")
    assert res.status_code == 200
    data = res.json()
    for key in [
        "summary", "tickets_by_priority", "tickets_by_category", "daily_trend",
        "avg_resolution_time_hours", "top_recurring_errors", "knowledge_usage",
        "resolution_rate_by_category",
    ]:
        assert key in data, f"missing {key}"


def test_dashboard_counts_reflect_database(client, db_session):
    _seed(db_session)
    data = client.get("/api/v1/analytics/dashboard").json()
    s = data["summary"]
    assert s["total_tickets"] == 2
    assert s["resolved_tickets"] == 1
    assert s["ai_resolution_rate"] == 50.0


def test_dashboard_top_recurring_errors_sorted(client, db_session):
    _seed(db_session)
    data = client.get("/api/v1/analytics/dashboard").json()
    errors = data["top_recurring_errors"]
    assert errors[0]["error_code"] == "ERR_VPN_AUTH_401"
    assert errors[0]["count"] == 2


def test_dashboard_avg_resolution_time(client, db_session):
    _seed(db_session)
    data = client.get("/api/v1/analytics/dashboard").json()
    # One resolved ticket with ~3h duration
    assert data["avg_resolution_time_hours"] > 0


def test_dashboard_knowledge_usage_empty(client, db_session):
    data = client.get("/api/v1/analytics/dashboard").json()
    ku = data["knowledge_usage"]
    assert ku["total_documents"] == 0
    assert ku["embedding_coverage"] == 0.0


def test_dashboard_knowledge_usage_with_docs(client, db_session):
    from app.rag.service import RAGService
    RAGService(db_session).ingest_document(title="Guide", category="Network", content="Some content here.", file_type="txt")
    data = client.get("/api/v1/analytics/dashboard").json()
    ku = data["knowledge_usage"]
    assert ku["total_documents"] == 1
    assert ku["total_chunks"] > 0
    assert ku["embedding_coverage"] == 100.0


def test_dashboard_daily_trend_includes_today(client, db_session):
    _seed(db_session)
    data = client.get("/api/v1/analytics/dashboard").json()
    # Tickets created "now" fall on today's bucket (UTC date)
    assert any(entry["count"] > 0 for entry in data["daily_trend"])


def test_summary_endpoint_matches_dashboard_summary(client, db_session):
    _seed(db_session)
    summary = client.get("/api/v1/analytics/").json()
    dash = client.get("/api/v1/analytics/dashboard").json()
    assert summary["total_tickets"] == dash["summary"]["total_tickets"]
    assert summary["ai_resolution_rate"] == dash["summary"]["ai_resolution_rate"]


def test_dashboard_days_param_validated(client):
    res = client.get("/api/v1/analytics/dashboard", params={"days": 5})
    assert res.status_code == 422
    res = client.get("/api/v1/analytics/dashboard", params={"days": 120})
    assert res.status_code == 422
