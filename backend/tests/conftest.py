import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.base import Base
import app.models  # Register all models into Base.metadata
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.device import Device

# Shared SQLite in-memory database across connections
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    # Override Vector type for SQLite in-memory test compatibility
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    # Add initial test user & device.
    # The seeded user acts as the bootstrap admin (password: testadmin123),
    # mirroring production where the first account is provisioned as admin.
    from app.core.security import get_password_hash
    user = User(
        email="test.user@acme-corp.com",
        full_name="Test User",
        role="admin",
        department="IT",
        hashed_password=get_password_hash("testadmin123"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    device = Device(user_id=user.id, device_name="Test Laptop", serial_number="TEST-12345", os="macOS", status="active")
    session.add(device)
    session.commit()
    session.refresh(device)

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def prevent_live_gemini_calls(monkeypatch):
    """Ensure no live Gemini API calls can ever occur in the test suite.

    Also switches the app to 'test' environment so the per-IP rate limiter
    does not throttle the many requests a single test can make.
    """
    from app.core.config import settings
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

