"""Tests for JWT authentication and role-based access control.

All Gemini calls are mocked by the autouse fixture in conftest.py.
"""
import pytest
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    normalize_role,
    verify_password,
)


def _register(client, email="engineer@acme-corp.com", password="S3curePass!x", full_name="Test Engineer", role="employee"):
    return client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": full_name, "role": role, "department": "IT",
    })


def _login(client, email="engineer@acme-corp.com", password="S3curePass!x"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Password hashing & tokens (unit)
# ---------------------------------------------------------------------------

def test_password_hash_and_verify():
    h = get_password_hash("my-secret-123")
    assert h != "my-secret-123"
    assert verify_password("my-secret-123", h)
    assert not verify_password("wrong-password", h)


def test_verify_password_fails_closed_without_hash():
    assert not verify_password("anything", None)


def test_token_roundtrip_contains_role():
    token = create_access_token(subject="42", role="support")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "support"


def test_invalid_token_rejected():
    assert decode_access_token("not-a-real-token") is None


def test_normalize_role_legacy_values():
    assert normalize_role("user") == "employee"
    assert normalize_role("technician") == "support"
    assert normalize_role("ADMIN") == "admin"
    assert normalize_role(None) == "employee"


# ---------------------------------------------------------------------------
# Registration & login (endpoint)
# ---------------------------------------------------------------------------

def test_register_creates_employee(client):
    res = _register(client)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "engineer@acme-corp.com"
    assert data["role"] == "employee"
    assert "hashed_password" not in data  # never leak the hash


def test_register_duplicate_email_conflict(client):
    _register(client)
    res = _register(client, email="engineer@acme-corp.com")
    assert res.status_code == 409


def test_register_cannot_self_assign_admin(client):
    """Non-first users may not self-register as admin/support."""
    res = _register(client, email="admin@acme-corp.com", role="admin")
    assert res.status_code == 201
    assert res.json()["role"] == "employee"


def test_login_success_returns_token(client):
    _register(client)
    res = _login(client)
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "engineer@acme-corp.com"


def test_login_wrong_password_unauthorized(client):
    _register(client)
    res = _login(client, password="wrong-password")
    assert res.status_code == 401


def test_login_unknown_email_unauthorized(client):
    res = _login(client, email="ghost@acme-corp.com")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# /me and password change
# ---------------------------------------------------------------------------

def test_me_requires_token(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_me_returns_current_user(client):
    _register(client)
    token = _login(client).json()["access_token"]
    res = client.get("/api/v1/auth/me", headers=_auth_headers(token))
    assert res.status_code == 200
    assert res.json()["email"] == "engineer@acme-corp.com"


def test_me_rejects_garbage_token(client):
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
    assert res.status_code == 401


def test_change_password_flow(client):
    _register(client)
    token = _login(client).json()["access_token"]
    res = client.post("/api/v1/auth/change-password", headers=_auth_headers(token),
                      json={"current_password": "S3curePass!x", "new_password": "N3wPassword!z"})
    assert res.status_code == 200
    # Old password no longer works, new one does
    assert _login(client).status_code == 401
    assert _login(client, password="N3wPassword!z").status_code == 200


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_token(client):
    """Login as the seeded bootstrap admin (provisioned by conftest)."""
    res = _login(client, email="test.user@acme-corp.com", password="testadmin123")
    assert res.status_code == 200
    return res.json()["access_token"]


def test_register_when_no_admin_exists_becomes_admin(client, db_session):
    """Bootstrap guarantee: with no admin in the system, the registrant is promoted."""
    # Remove the seeded admin to simulate a fresh system.
    from app.models.user import User as UserModel
    db_session.query(UserModel).delete()
    db_session.commit()

    res = _register(client, email="boss@acme-corp.com")
    assert res.status_code == 201
    assert res.json()["role"] == "admin"


def test_admin_can_list_users(client, admin_token):
    res = client.get("/api/v1/auth/users", headers=_auth_headers(admin_token))
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_employee_cannot_list_users(client):
    _register(client)
    token = _login(client).json()["access_token"]
    res = client.get("/api/v1/auth/users", headers=_auth_headers(token))
    assert res.status_code == 403


def test_admin_can_create_support_user(client, admin_token):
    res = client.post("/api/v1/auth/users", headers=_auth_headers(admin_token), json={
        "email": "tech@acme-corp.com", "password": "TechPass!123", "full_name": "Tech", "role": "support",
    })
    assert res.status_code == 201
    assert res.json()["role"] == "support"


def test_admin_can_update_user_role(client, admin_token):
    client.post("/api/v1/auth/users", headers=_auth_headers(admin_token), json={
        "email": "promote@acme-corp.com", "password": "Promote!123", "full_name": "P", "role": "employee",
    })
    users = client.get("/api/v1/auth/users", headers=_auth_headers(admin_token)).json()
    target = next(u for u in users if u["email"] == "promote@acme-corp.com")
    res = client.patch(f"/api/v1/auth/users/{target['id']}", headers=_auth_headers(admin_token),
                       json={"role": "support"})
    assert res.status_code == 200
    assert res.json()["role"] == "support"


def test_admin_cannot_deactivate_self(client, admin_token):
    me = client.get("/api/v1/auth/me", headers=_auth_headers(admin_token)).json()
    res = client.patch(f"/api/v1/auth/users/{me['id']}", headers=_auth_headers(admin_token),
                       json={"is_active": False})
    assert res.status_code == 400


def test_disabled_user_cannot_authenticate(client, admin_token):
    client.post("/api/v1/auth/users", headers=_auth_headers(admin_token), json={
        "email": "disable@acme-corp.com", "password": "Disable!123", "full_name": "D", "role": "employee",
    })
    users = client.get("/api/v1/auth/users", headers=_auth_headers(admin_token)).json()
    target = next(u for u in users if u["email"] == "disable@acme-corp.com")
    client.patch(f"/api/v1/auth/users/{target['id']}", headers=_auth_headers(admin_token), json={"is_active": False})
    res = _login(client, email="disable@acme-corp.com", password="Disable!123")
    assert res.status_code == 403
