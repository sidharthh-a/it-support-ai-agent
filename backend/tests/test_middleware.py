"""Tests for production-hardening middleware and health endpoints."""
import pytest

from app.core.config import Settings, DEFAULT_DEV_SECRET_KEY


def test_request_id_header_returned(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID")


def test_request_id_includes_incoming_value(client):
    res = client.get("/api/v1/health", headers={"X-Request-ID": "my-trace-42"})
    assert res.headers.get("X-Request-ID") == "my-trace-42"


def test_security_headers_present(client):
    res = client.get("/api/v1/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_liveness_endpoint(client):
    res = client.get("/api/v1/live")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_readiness_endpoint(client):
    res = client.get("/api/v1/ready")
    assert res.status_code == 200
    assert res.json()["status"] in ("ready", "degraded")


def test_health_detailed_payload(client):
    res = client.get("/api/v1/health")
    data = res.json()
    assert data["status"] == "ok"
    assert data["embedding"]["dimension"] == 384
    assert data["llm"]["gemini_configured"] is False  # mocked out in tests


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def test_config_rejects_bad_environment():
    with pytest.raises(ValueError, match="ENVIRONMENT"):
        Settings(ENVIRONMENT="nonsense-env")


def test_config_rejects_bad_embedding_provider():
    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER"):
        Settings(EMBEDDING_PROVIDER="huggingface")


def test_config_rejects_bad_embedding_dimension():
    with pytest.raises(ValueError, match="EMBEDDING_DIMENSION"):
        Settings(EMBEDDING_DIMENSION=0)
    with pytest.raises(ValueError, match="EMBEDDING_DIMENSION"):
        Settings(EMBEDDING_DIMENSION=9999)


def test_config_rejects_wildcard_cors_in_production():
    with pytest.raises(ValueError, match="Wildcard"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="x" * 20,
            BACKEND_CORS_ORIGINS=["*"],
        )


def test_config_accepts_production_cors_allowlist():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="x" * 20,
        BACKEND_CORS_ORIGINS=["https://support.example.com"],
    )
    assert s.BACKEND_CORS_ORIGINS == ["https://support.example.com"]


def test_config_default_embedding_dimension_is_384():
    s = Settings()
    assert s.EMBEDDING_DIMENSION == 384
