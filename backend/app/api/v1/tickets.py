from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.deps import get_current_user, get_current_user_optional
from app.core.security import normalize_role, ROLE_SUPPORT, ROLE_ADMIN
from app.models.user import User
from app.repositories.ticket_repository import TicketRepository
from app.schemas.ticket import TicketCreate, TicketUpdate, TicketRead, TicketHistoryRead, TicketCommentCreate, TicketCommentRead
from app.schemas.error_log import ErrorLogRead

router = APIRouter()


def _user_can_manage(user: Optional[User]) -> bool:
    return user is not None and normalize_role(user.role) in (ROLE_SUPPORT, ROLE_ADMIN)


@router.get("/", response_model=List[TicketRead])
def list_tickets(
    query: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    repo = TicketRepository(db)
    # Employees only see their own tickets; support/admin see all.
    user_id_filter = None
    if current_user is not None and not _user_can_manage(current_user):
        user_id_filter = current_user.id
    return repo.search_tickets(
        query=query, status=status, priority=priority, category=category,
        user_id=user_id_filter, assigned_to_id=assigned_to_id, limit=limit,
    )


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    repo = TicketRepository(db)
    ticket = repo.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_user is not None and not _user_can_manage(current_user) and ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to view this ticket")
    return ticket


@router.post("/", response_model=TicketRead, status_code=201)
def create_ticket(
    ticket_in: TicketCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user is not None:
        ticket_in.user_id = current_user.id
    repo = TicketRepository(db)
    return repo.create_ticket(ticket_in)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int,
    update_in: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    repo = TicketRepository(db)
    ticket = repo.get_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    # Employees may only update their own tickets' title/description; staff manage everything.
    if current_user is not None and not _user_can_manage(current_user):
        if ticket.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You do not have permission to update this ticket")
        allowed = {"title", "description"}
        if set(update_in.model_dump(exclude_unset=True).keys()) - allowed:
            raise HTTPException(status_code=403, detail="Only support staff can change status, priority, or assignment")
    if current_user is not None:
        update_in.changed_by_id = current_user.id
    updated = repo.update_ticket(ticket_id, update_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return updated


@router.post("/{ticket_id}/escalate", response_model=TicketRead)
def escalate_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Escalate a ticket: sets status=escalated and priority=critical (if lower)."""
    if not _user_can_manage(current_user):
        raise HTTPException(status_code=403, detail="Only support staff can escalate tickets")
    repo = TicketRepository(db)
    update_in = TicketUpdate(status="escalated", priority="critical", changed_by_id=current_user.id if current_user else None)
    updated = repo.update_ticket(ticket_id, update_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return updated


@router.get("/{ticket_id}/history", response_model=List[TicketHistoryRead])
def get_ticket_history(ticket_id: int, db: Session = Depends(get_db)):
    repo = TicketRepository(db)
    return repo.get_history(ticket_id)


@router.get("/{ticket_id}/comments", response_model=List[TicketCommentRead])
def get_ticket_comments(ticket_id: int, db: Session = Depends(get_db)):
    repo = TicketRepository(db)
    if not repo.get_by_id(ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return repo.get_comments(ticket_id)


@router.post("/{ticket_id}/comments", response_model=TicketCommentRead, status_code=201)
def add_ticket_comment(
    ticket_id: int,
    payload: TicketCommentCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    repo = TicketRepository(db)
    if not repo.get_by_id(ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    comment = repo.add_comment(ticket_id, payload.body, author_id=current_user.id if current_user else None)
    if comment is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return comment


@router.get("/{ticket_id}/logs", response_model=List[ErrorLogRead])
def get_ticket_related_logs(
    ticket_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Error logs related to this ticket (ticket detail page)."""
    repo = TicketRepository(db)
    if not repo.get_by_id(ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return repo.get_related_error_logs(ticket_id, limit=limit)
