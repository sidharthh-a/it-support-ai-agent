from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class IncidentBase(BaseModel):
    title: str
    description: str
    severity: str = "P3"
    status: str = "investigating"
    affected_service: str


class IncidentCreate(IncidentBase):
    ticket_id: Optional[int] = None


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    affected_service: Optional[str] = None
    ticket_id: Optional[int] = None
    resolved_at: Optional[datetime] = None


class IncidentRead(IncidentBase):
    id: int
    ticket_id: Optional[int] = None
    started_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
