from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, normalize_role


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        stmt = select(User).order_by(User.id).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, user_in: UserCreate, password: Optional[str] = None) -> User:
        user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            role=normalize_role(user_in.role),
            department=user_in.department,
            hashed_password=get_password_hash(password) if password else None,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User, **fields) -> User:
        """Apply arbitrary whitelisted field updates (caller validates fields)."""
        password = fields.pop("password", None)
        if password:
            user.hashed_password = get_password_hash(password)
        for field, value in fields.items():
            if value is not None and hasattr(user, field):
                if field == "role":
                    value = normalize_role(value)
                setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user
