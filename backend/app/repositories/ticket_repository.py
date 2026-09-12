import random
import string
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, or_, func
from app.models.ticket import SupportTicket
from app.models.ticket_history import TicketHistory
from app.models.resolution import Resolution
from app.models.ticket_comment import TicketComment
from app.models.error_log import ErrorLog
from app.schemas.ticket import TicketCreate, TicketUpdate


class TicketRepository:
    def __init__(self, db: Session):
        self.db = db

    def _generate_ticket_number(self) -> str:
        count = self.db.query(func.count(SupportTicket.id)).scalar() or 0
        return f"TICK-{1000 + count + 1}"

    def get_by_id(self, ticket_id: int) -> Optional[SupportTicket]:
        stmt = (
            select(SupportTicket)
            .options(
                joinedload(SupportTicket.creator),
                joinedload(SupportTicket.assignee),
                joinedload(SupportTicket.device),
                joinedload(SupportTicket.resolution),
                joinedload(SupportTicket.history)
            )
            .where(SupportTicket.id == ticket_id)
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_by_ticket_number(self, ticket_number: str) -> Optional[SupportTicket]:
        stmt = (
            select(SupportTicket)
            .options(
                joinedload(SupportTicket.creator),
                joinedload(SupportTicket.assignee),
                joinedload(SupportTicket.device),
                joinedload(SupportTicket.resolution),
                joinedload(SupportTicket.history)
            )
            .where(SupportTicket.ticket_number == ticket_number)
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def search_tickets(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[int] = None,
        assigned_to_id: Optional[int] = None,
        limit: int = 50
    ) -> List[SupportTicket]:
        stmt = select(SupportTicket).options(
            joinedload(SupportTicket.creator),
            joinedload(SupportTicket.assignee),
            joinedload(SupportTicket.device)
        )

        filters = []
        if query:
            search_pattern = f"%{query}%"
            filters.append(
                or_(
                    SupportTicket.title.ilike(search_pattern),
                    SupportTicket.description.ilike(search_pattern),
                    SupportTicket.ticket_number.ilike(search_pattern)
                )
            )
        if status:
            filters.append(SupportTicket.status == status)
        if priority:
            filters.append(SupportTicket.priority == priority)
        if category:
            filters.append(SupportTicket.category == category)
        if user_id:
            filters.append(SupportTicket.user_id == user_id)
        if assigned_to_id:
            filters.append(SupportTicket.assigned_to_id == assigned_to_id)

        if filters:
            stmt = stmt.where(*filters)

        stmt = stmt.order_by(SupportTicket.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).unique().scalars().all())

    def create_ticket(self, ticket_in: TicketCreate) -> SupportTicket:
        ticket_num = self._generate_ticket_number()
        ticket = SupportTicket(
            ticket_number=ticket_num,
            title=ticket_in.title,
            description=ticket_in.description,
            priority=ticket_in.priority,
            category=ticket_in.category,
            status="open",
            user_id=ticket_in.user_id,
            assigned_to_id=ticket_in.assigned_to_id,
            device_id=ticket_in.device_id,
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        # Initial history record
        history = TicketHistory(
            ticket_id=ticket.id,
            changed_by_id=ticket_in.user_id,
            field_changed="status",
            old_value=None,
            new_value="open"
        )
        self.db.add(history)
        self.db.commit()
        
        return self.get_by_id(ticket.id)  # return fully loaded

    def update_ticket(self, ticket_id: int, update_in: TicketUpdate) -> Optional[SupportTicket]:
        ticket = self.db.get(SupportTicket, ticket_id)
        if not ticket:
            return None

        update_data = update_in.model_dump(exclude_unset=True)
        changed_by_id = update_data.pop("changed_by_id", None) or ticket.user_id

        for field, new_val in update_data.items():
            old_val = getattr(ticket, field)
            if str(old_val) != str(new_val):
                setattr(ticket, field, new_val)
                history = TicketHistory(
                    ticket_id=ticket.id,
                    changed_by_id=changed_by_id,
                    field_changed=field,
                    old_value=str(old_val) if old_val is not None else None,
                    new_value=str(new_val) if new_val is not None else None
                )
                self.db.add(history)

        ticket.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return self.get_by_id(ticket.id)

    def get_history(self, ticket_id: int) -> List[TicketHistory]:
        stmt = (
            select(TicketHistory)
            .options(joinedload(TicketHistory.changed_by))
            .where(TicketHistory.ticket_id == ticket_id)
            .order_by(TicketHistory.timestamp.asc())
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------
    def add_comment(self, ticket_id: int, body: str, author_id: Optional[int] = None) -> Optional[TicketComment]:
        ticket = self.db.get(SupportTicket, ticket_id)
        if not ticket:
            return None
        comment = TicketComment(ticket_id=ticket_id, author_id=author_id, body=body)
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def get_comments(self, ticket_id: int) -> List[TicketComment]:
        stmt = (
            select(TicketComment)
            .options(joinedload(TicketComment.author))
            .where(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.created_at.asc())
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    # ------------------------------------------------------------------
    # Related evidence for the ticket detail page
    # ------------------------------------------------------------------
    def get_related_error_logs(self, ticket_id: int, limit: int = 20) -> List[ErrorLog]:
        stmt = (
            select(ErrorLog)
            .where(ErrorLog.ticket_id == ticket_id)
            .order_by(ErrorLog.timestamp.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
