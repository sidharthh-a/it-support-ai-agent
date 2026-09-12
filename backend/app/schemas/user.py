from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field

from app.core.security import ROLE_EMPLOYEE


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str = ROLE_EMPLOYEE
    department: str = "General"


class UserCreate(UserBase):
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserAdminCreate(UserBase):
    """Admin-created users may be assigned any role and must have a password."""
    password: str = Field(min_length=8, max_length=128)


class UserAdminUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    department: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
