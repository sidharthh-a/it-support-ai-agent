from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.security import (
    ROLE_ADMIN,
    ROLE_EMPLOYEE,
    ROLE_SUPPORT,
    get_password_hash,
    normalize_role,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    LoginRequest,
    PasswordChange,
    TokenResponse,
    UserAdminCreate,
    UserAdminUpdate,
    UserCreate,
    UserRead,
)
from app.core.config import settings
from app.core.security import ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email + password and receive a JWT access token."""
    repo = UserRepository(db)
    user = repo.get_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")

    token = _create_token_for_user(user)
    return TokenResponse(access_token=token, expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60, user=UserRead.model_validate(user))


@router.post("/register", response_model=UserRead, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Self-service registration with a bootstrap guarantee:

    - If no admin exists yet, the first registered user is promoted to admin
      so the system is always administrable.
    - Once an admin exists, self-registration can never grant elevated roles.
    """
    repo = UserRepository(db)
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    from sqlalchemy import select, func
    admin_exists = (
        db.scalar(select(func.count(User.id)).where(User.role == ROLE_ADMIN)) or 0
    ) > 0

    if not admin_exists:
        role = ROLE_ADMIN
    else:
        requested = normalize_role(payload.role)
        role = ROLE_EMPLOYEE if requested in (ROLE_SUPPORT, ROLE_ADMIN) else requested

    user = repo.create(payload, password=payload.password or "changeme123")
    if role != user.role:
        user = repo.update(user, role=role)
    return user


@router.get("/me", response_model=UserRead)
def read_current_user(current_user=Depends(get_current_user)):
    return current_user


@router.post("/change-password", response_model=UserRead)
def change_password(
    payload: PasswordChange,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    stored = repo.get_by_id(current_user.id)
    if stored is None or not verify_password(payload.current_password, stored.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    updated = repo.update(stored, password=payload.new_password)
    return updated


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[UserRead])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user=Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    return UserRepository(db).get_all(skip=skip, limit=limit)


@router.post("/users", response_model=UserRead, status_code=201)
def create_user(
    payload: UserAdminCreate,
    current_user=Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return repo.create(payload, password=payload.password)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserAdminUpdate,
    current_user=Depends(require_roles(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    fields = payload.model_dump(exclude_unset=True)
    if user.id == current_user.id and fields.get("is_active") is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    return repo.update(user, **fields)


def _create_token_for_user(user) -> str:
    from app.core.security import create_access_token
    return create_access_token(subject=str(user.id), role=user.role)
