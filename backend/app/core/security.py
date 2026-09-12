"""
Security utilities: password hashing (bcrypt) and JWT tokens.

Roles are canonical: "admin", "support", "employee".
Legacy role values ("user", "technician") are normalised on read.

Note: bcrypt has a 72-byte input limit; longer passwords are truncated
consistently on both hash and verify (standard practice).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import jwt, JWTError

from app.core.config import settings

# Canonical role names used across backend and frontend.
ROLE_ADMIN = "admin"
ROLE_SUPPORT = "support"
ROLE_EMPLOYEE = "employee"

_LEGACY_ROLE_MAP = {
    "user": ROLE_EMPLOYEE,
    "technician": ROLE_SUPPORT,
    "technican": ROLE_SUPPORT,
    "admin": ROLE_ADMIN,
    "support": ROLE_SUPPORT,
    "employee": ROLE_EMPLOYEE,
}

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12 hours
TOKEN_TYPE_KEY = "type"
TOKEN_TYPE_ACCESS = "access"

_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def normalize_role(role: Optional[str]) -> str:
    """Map any historical/legacy role string to the canonical set."""
    if not role:
        return ROLE_EMPLOYEE
    return _LEGACY_ROLE_MAP.get(role.strip().lower(), ROLE_EMPLOYEE)


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Constant-time password verification; fails closed when no hash exists."""
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain_password), hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(
    subject: str,
    role: str = ROLE_EMPLOYEE,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        "sub": subject,
        "role": normalize_role(role),
        "iat": now,
        "exp": now + expires_delta,
        TOKEN_TYPE_KEY: TOKEN_TYPE_ACCESS,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT; returns None when invalid/expired."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get(TOKEN_TYPE_KEY) != TOKEN_TYPE_ACCESS:
        return None
    if payload.get("sub") is None:
        return None
    return payload
