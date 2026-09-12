"""FastAPI authentication dependencies: JWT bearer parsing and RBAC guards."""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import (
    ROLE_ADMIN,
    ROLE_SUPPORT,
    decode_access_token,
    normalize_role,
)
from app.db.session import get_db
from app.models.user import User

# tokenUrl points at the OAuth2 password-flow login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/v1/auth/login", auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Bearer token."""
    if not token:
        raise _unauthorized()
    payload = decode_access_token(token)
    if payload is None:
        raise _unauthorized("Invalid or expired token")

    subject = payload.get("sub")
    user = None
    if isinstance(subject, str) and subject.isdigit():
        user = db.get(User, int(subject))
    if user is None:
        email = payload.get("email")
        if email:
            from app.repositories.user_repository import UserRepository
            user = UserRepository(db).get_by_email(email)
    if user is None:
        raise _unauthorized("User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Resolve the user when a token is present; returns None for anonymous requests.

    Used to keep legacy endpoints functional during migration.
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    subject = payload.get("sub")
    if isinstance(subject, str) and subject.isdigit():
        return db.get(User, int(subject))
    return None


def require_roles(*roles: str):
    """Dependency factory enforcing that the current user has one of the given roles."""
    allowed = {normalize_role(r) for r in roles}

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if normalize_role(current_user.role) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return _dependency


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    return require_roles(ROLE_ADMIN)(current_user)


def require_support_or_admin(current_user: User = Depends(get_current_user)) -> User:
    return require_roles(ROLE_SUPPORT, ROLE_ADMIN)(current_user)
