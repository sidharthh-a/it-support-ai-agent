from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ErrorLogBase(BaseModel):
    service_name: str
    error_code: str
    log_message: str
    stack_trace: Optional[str] = None


class ErrorLogCreate(ErrorLogBase):
    device_id: Optional[int] = None
    ticket_id: Optional[int] = None


class ErrorLogRead(ErrorLogBase):
    id: int
    device_id: Optional[int] = None
    ticket_id: Optional[int] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
