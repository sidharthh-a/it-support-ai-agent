from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.user import UserRead


class DeviceBase(BaseModel):
    device_name: str
    serial_number: str
    os: str
    status: str = "active"
    ip_address: Optional[str] = None


class DeviceCreate(DeviceBase):
    user_id: Optional[int] = None


class DeviceRead(DeviceBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    user: Optional[UserRead] = None

    model_config = ConfigDict(from_attributes=True)
