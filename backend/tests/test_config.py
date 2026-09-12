import pytest
from app.core.config import Settings, DEFAULT_DEV_SECRET_KEY


def test_development_config_defaults():
    """Test that development environment works with non-empty secret key."""
    s = Settings(ENVIRONMENT="development")
    assert s.SECRET_KEY
    assert isinstance(s.BACKEND_CORS_ORIGINS, list)


def test_production_config_rejects_default_secret_key():
    """Test that production environment rejects default dev secret key."""
    with pytest.raises(ValueError, match="SECRET_KEY must be explicitly set"):
        Settings(ENVIRONMENT="production", SECRET_KEY=DEFAULT_DEV_SECRET_KEY)


def test_production_config_accepts_custom_secret_key():
    """Test that production environment accepts a custom secret key."""
    s = Settings(ENVIRONMENT="production", SECRET_KEY="my-prod-custom-secure-secret-key-123")
    assert s.SECRET_KEY == "my-prod-custom-secure-secret-key-123"


def test_cors_origins_parsing_comma_separated():
    """Test parsing of comma-separated string for BACKEND_CORS_ORIGINS."""
    s = Settings(BACKEND_CORS_ORIGINS="http://localhost:3000,https://app.example.com")
    assert s.BACKEND_CORS_ORIGINS == ["http://localhost:3000", "https://app.example.com"]


def test_cors_origins_comma_separated_from_env_var_source(monkeypatch):
    """Regression: Docker Compose passes BACKEND_CORS_ORIGINS as a comma-separated
    process environment variable. pydantic-settings JSON-decodes complex fields
    sourced from env vars, which crashed container startup with SettingsError
    (json.JSONDecodeError). The NoDecode annotation + validator must handle it."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    s = Settings()
    assert s.BACKEND_CORS_ORIGINS == ["http://localhost:3000", "http://localhost:5173"]


def test_cors_origins_json_form_from_env_var_source(monkeypatch):
    """JSON array form from a process env var must keep working."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", '["http://a.example", "https://b.example"]')
    s = Settings()
    assert s.BACKEND_CORS_ORIGINS == ["http://a.example", "https://b.example"]
