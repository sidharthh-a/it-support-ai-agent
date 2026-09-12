from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_
from app.models.device import Device
from app.schemas.device import DeviceCreate


class DeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, device_id: int) -> Optional[Device]:
        stmt = select(Device).options(joinedload(Device.user)).where(Device.id == device_id)
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_all(self, limit: int = 100) -> List[Device]:
        stmt = select(Device).options(joinedload(Device.user)).order_by(Device.id.desc()).limit(limit)
        return list(self.db.execute(stmt).unique().scalars().all())

    def search_devices(self, query: str) -> List[Device]:
        search_pattern = f"%{query}%"
        stmt = (
            select(Device)
            .options(joinedload(Device.user))
            .where(
                or_(
                    Device.device_name.ilike(search_pattern),
                    Device.serial_number.ilike(search_pattern),
                    Device.os.ilike(search_pattern),
                    Device.ip_address.ilike(search_pattern)
                )
            )
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def create(self, device_in: DeviceCreate) -> Device:
        device = Device(
            user_id=device_in.user_id,
            device_name=device_in.device_name,
            serial_number=device_in.serial_number,
            os=device_in.os,
            status=device_in.status,
            ip_address=device_in.ip_address
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        return self.get_by_id(device.id)
