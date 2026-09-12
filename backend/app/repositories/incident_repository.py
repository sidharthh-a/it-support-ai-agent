from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentUpdate


class IncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, limit: int = 50) -> List[Incident]:
        stmt = select(Incident).options(joinedload(Incident.ticket)).order_by(Incident.started_at.desc()).limit(limit)
        return list(self.db.execute(stmt).unique().scalars().all())

    def get_by_id(self, incident_id: int) -> Optional[Incident]:
        stmt = select(Incident).options(joinedload(Incident.ticket)).where(Incident.id == incident_id)
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def create(self, incident_in: IncidentCreate) -> Incident:
        incident = Incident(
            title=incident_in.title,
            description=incident_in.description,
            severity=incident_in.severity,
            status=incident_in.status,
            affected_service=incident_in.affected_service,
            ticket_id=incident_in.ticket_id
        )
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return self.get_by_id(incident.id)

    def update(self, incident_id: int, update_in: IncidentUpdate) -> Optional[Incident]:
        incident = self.db.get(Incident, incident_id)
        if not incident:
            return None
        data = update_in.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(incident, field, value)
        self.db.commit()
        return self.get_by_id(incident.id)
