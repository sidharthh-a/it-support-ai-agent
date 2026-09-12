from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.user import UserRead
from app.schemas.device import DeviceRead


class TicketCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class TicketCommentRead(BaseModel):
    id: int
    ticket_id: int
    author_id: Optional[int] = None
    body: str
    created_at: datetime
    author: Optional[UserRead] = None

    model_config = ConfigDict(from_attributes=True)


class TicketHistoryRead(BaseModel):
    id: int
    ticket_id: int
    changed_by_id: Optional[int] = None
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    timestamp: datetime
    changed_by: Optional[UserRead] = None

    model_config = ConfigDict(from_attributes=True)


class ResolutionRead(BaseModel):
    id: int
    ticket_id: int
    solution_summary: str
    steps_taken: str
    resolved_by_id: int
    resolved_at: datetime
    resolved_by: Optional[UserRead] = None

    model_config = ConfigDict(from_attributes=True)


class TicketBase(BaseModel):
    title: str
    description: str
    priority: str = "medium"
    category: str = "software"


class TicketCreate(TicketBase):
    user_id: int
    assigned_to_id: Optional[int] = None
    device_id: Optional[int] = None


class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    assigned_to_id: Optional[int] = None
    device_id: Optional[int] = None
    changed_by_id: Optional[int] = None


class TicketRead(TicketBase):
    id: int
    ticket_number: str
    status: str
    user_id: int
    assigned_to_id: Optional[int] = None
    device_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    creator: Optional[UserRead] = None
    assignee: Optional[UserRead] = None
    device: Optional[DeviceRead] = None
    resolution: Optional[ResolutionRead] = None
    history: List[TicketHistoryRead] = []
    comments: List[TicketCommentRead] = []

    model_config = ConfigDict(from_attributes=True)
