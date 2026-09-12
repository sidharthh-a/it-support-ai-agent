from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.repositories.incident_repository import IncidentRepository
from app.schemas.incident import IncidentCreate, IncidentUpdate, IncidentRead

router = APIRouter()


@router.get("/", response_model=List[IncidentRead])
def list_incidents(db: Session = Depends(get_db)):
    repo = IncidentRepository(db)
    return repo.get_all()


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    repo = IncidentRepository(db)
    incident = repo.get_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/", response_model=IncidentRead, status_code=201)
def create_incident(incident_in: IncidentCreate, db: Session = Depends(get_db)):
    repo = IncidentRepository(db)
    return repo.create(incident_in)


@router.patch("/{incident_id}", response_model=IncidentRead)
def update_incident(incident_id: int, update_in: IncidentUpdate, db: Session = Depends(get_db)):
    repo = IncidentRepository(db)
    updated = repo.update(incident_id, update_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Incident not found")
    return updated
