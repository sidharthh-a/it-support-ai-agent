"""Tests for admin panel endpoints with RBAC enforcement."""
import pytest
from app.rag.service import RAGService


def _login(client, email="test.user@acme-corp.com", password="testadmin123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _employee_headers(client):
    client.post("/api/v1/auth/register", json={
        "email": "emp@acme-corp.com", "password": "S3curePass!x", "full_name": "E", "role": "employee", "department": "IT",
    })
    res = client.post("/api/v1/auth/login", json={"email": "emp@acme-corp.com", "password": "S3curePass!x"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_admin_system_info(client):
    headers = _login(client)
    res = client.get("/api/v1/admin/system", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("ok", "degraded")
    assert data["embedding"]["dimension"] == 384
    assert data["embedding"]["provider"] == "local"
    assert "gemini_model" in data["llm"]
    assert "database" in data


def test_admin_system_info_requires_admin(client):
    headers = _employee_headers(client)
    res = client.get("/api/v1/admin/system", headers=headers)
    assert res.status_code == 403


def test_admin_system_info_requires_auth(client):
    res = client.get("/api/v1/admin/system")
    assert res.status_code == 401


def test_admin_reindex_all(client, db_session):
    rag = RAGService(db_session)
    rag.ingest_document(title="Doc A", category="Network", content="Content alpha for reindex test.", file_type="txt")
    headers = _login(client)
    res = client.post("/api/v1/admin/reindex-all", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["reindexed"] > 0
    assert data["skipped"] == 0
    assert data["dimension"] == 384


def test_admin_reindex_all_requires_admin(client):
    headers = _employee_headers(client)
    res = client.post("/api/v1/admin/reindex-all", headers=headers)
    assert res.status_code == 403


def test_admin_user_management(client):
    headers = _login(client)
    # Create
    res = client.post("/api/v1/admin/users", headers=headers, json={
        "email": "new@acme-corp.com", "password": "NewPass!123", "full_name": "New", "role": "support",
    })
    assert res.status_code == 201
    assert res.json()["role"] == "support"
    # List
    res = client.get("/api/v1/admin/users", headers=headers)
    assert res.status_code == 200
    assert any(u["email"] == "new@acme-corp.com" for u in res.json())


def test_admin_logs_endpoint(client, db_session):
    db_session.add(__import__("app.models.error_log", fromlist=["ErrorLog"]).ErrorLog(
        service_name="svc", error_code="ERR_TEST_X", log_message="test log"))
    db_session.commit()
    headers = _login(client)
    res = client.get("/api/v1/admin/logs", headers=headers)
    assert res.status_code == 200
    logs = res.json()
    assert any(l["error_code"] == "ERR_TEST_X" for l in logs)


def test_admin_logs_require_admin(client):
    headers = _employee_headers(client)
    res = client.get("/api/v1/admin/logs", headers=headers)
    assert res.status_code == 403
