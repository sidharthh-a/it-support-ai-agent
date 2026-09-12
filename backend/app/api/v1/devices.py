from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.repositories.device_repository import DeviceRepository
from app.schemas.device import DeviceCreate, DeviceRead

router = APIRouter()


@router.get("/", response_model=List[DeviceRead])
def list_devices(
    query: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    repo = DeviceRepository(db)
    if query:
        return repo.search_devices(query)
    return repo.get_all(limit=limit)


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(device_id: int, db: Session = Depends(get_db)):
    repo = DeviceRepository(db)
    device = repo.get_by_id(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/", response_model=DeviceRead, status_code=201)
def create_device(device_in: DeviceCreate, db: Session = Depends(get_db)):
    repo = DeviceRepository(db)
    return repo.create(device_in)
