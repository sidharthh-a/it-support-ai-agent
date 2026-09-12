import re
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.repositories.ticket_repository import TicketRepository
from app.repositories.error_log_repository import ErrorLogRepository
from app.rag.service import RAGService
from app.schemas.ticket import TicketCreate, TicketUpdate


def extract_error_code(text: Optional[str]) -> Optional[str]:
    """Extract standard IT error codes (e.g., ERR_VPN_AUTH_401, ERR_AUTH_403, ERR_NETWORK_500) from text."""
    if not text:
        return None
    match = re.search(r"\bERR(?:OR)?_[A-Z0-9_]+\b", text, re.IGNORECASE)
    return match.group(0).upper() if match else None


class SearchDocumentsInput(BaseModel):
    query: str = Field(description="Search term or problem description to query knowledge base docs")
    limit: int = Field(default=5, description="Maximum number of knowledge chunks to return")


class SearchTicketsInput(BaseModel):
    query: Optional[str] = Field(default=None, description="Keywords to match in ticket title or description")
    status: Optional[str] = Field(default=None, description="Filter by status: open, in_progress, resolved, closed, escalated")
    priority: Optional[str] = Field(default=None, description="Filter by priority: low, medium, high, critical")
    category: Optional[str] = Field(default=None, description="Filter by category: network, hardware, software, access, security")


class TicketHistoryInput(BaseModel):
    ticket_id: int = Field(description="ID of the ticket to fetch change history for")


class SearchErrorLogsInput(BaseModel):
    query: Optional[str] = Field(default=None, description="Keyword search in log message or stack trace")
    service_name: Optional[str] = Field(default=None, description="Filter by service name (e.g. auth-service, vpn-gateway)")
    error_code: Optional[str] = Field(default=None, description="Filter by error code (e.g. ERR_VPN_AUTH_01, ERR_DB_CONN)")


class CreateTicketInput(BaseModel):
    title: str = Field(description="Short descriptive title of the support ticket")
    description: str = Field(description="Detailed explanation of the IT problem")
    priority: str = Field(default="medium", description="Priority level: low, medium, high, critical")
    category: str = Field(default="software", description="Category: network, hardware, software, access, security")
    user_id: int = Field(default=1, description="User ID creating the ticket")
    device_id: Optional[int] = Field(default=None, description="Optional associated device ID")


class UpdateTicketInput(BaseModel):
    ticket_id: int = Field(description="ID of the ticket to update")
    status: Optional[str] = Field(default=None, description="New status: open, in_progress, resolved, closed, escalated")
    priority: Optional[str] = Field(default=None, description="New priority: low, medium, high, critical")
    title: Optional[str] = Field(default=None, description="Updated title")
    description: Optional[str] = Field(default=None, description="Updated description")


def create_agent_tools(db: Session):
    ticket_repo = TicketRepository(db)
    error_repo = ErrorLogRepository(db)
    rag_service = RAGService(db)

    @tool("search_documents", args_schema=SearchDocumentsInput)
    def search_documents(query: str, limit: int = 5) -> str:
        """Search technical knowledge base documents using RAG vector similarity."""
        results = rag_service.search_knowledge(query, limit=limit)
        if not results:
            return "No matching technical documentation found."
        
        output = []
        for r in results:
            output.append(f"Document: {r['title']} (Category: {r['category']})\nContent: {r['content']}\n")
        return "\n---\n".join(output)

    @tool("search_tickets", args_schema=SearchTicketsInput)
    def search_tickets(
        query: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None
    ) -> str:
        """Query existing IT support tickets in PostgreSQL by query keywords, status, priority, or category."""
        search_query = query
        if query and not status and not priority and not category:
            code = extract_error_code(query)
            if code:
                search_query = code

        tickets = ticket_repo.search_tickets(query=search_query, status=status, priority=priority, category=category, limit=3)
        if not tickets:
            return "No support tickets match the given criteria."

        res = []
        for t in tickets[:3]:
            creator_name = t.creator.full_name if t.creator else "User"
            res.append(
                f"- Ticket #{t.ticket_number} (Status: {t.status}, Priority: {t.priority}, User: {creator_name}): {t.title}\n  Description: {t.description[:150]}"
            )
        return f"Found {len(tickets[:3])} matching historical ticket(s):\n" + "\n".join(res)

    @tool("get_ticket_history", args_schema=TicketHistoryInput)
    def get_ticket_history(ticket_id: int) -> str:
        """Retrieve audit change history for a given ticket ID."""
        ticket = ticket_repo.get_by_id(ticket_id)
        if not ticket:
            return f"Ticket ID {ticket_id} not found."
        
        history = ticket_repo.get_history(ticket_id)
        if not history:
            return f"No change history found for Ticket #{ticket.ticket_number}."

        res = [f"History for Ticket #{ticket.ticket_number}:"]
        for h in history:
            changed_by = h.changed_by.full_name if h.changed_by else "System"
            res.append(f"[{h.timestamp.strftime('%Y-%m-%d %H:%M')}] Field '{h.field_changed}' changed from '{h.old_value}' to '{h.new_value}' by {changed_by}")
        return "\n".join(res)

    @tool("search_error_logs", args_schema=SearchErrorLogsInput)
    def search_error_logs(
        query: Optional[str] = None,
        service_name: Optional[str] = None,
        error_code: Optional[str] = None
    ) -> str:
        """Search system error logs for relevant error codes, log messages, or affected services."""
        search_code = error_code
        search_query = query
        if query and not error_code:
            code = extract_error_code(query)
            if code:
                search_code = code
                search_query = None

        logs = error_repo.search_error_logs(query=search_query, service_name=service_name, error_code=search_code, limit=10)
        if not logs:
            return "No matching error logs found."

        res = []
        for l in logs:
            res.append(
                f"[{l.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Service: {l.service_name} | Code: {l.error_code}\nMessage: {l.log_message}"
            )
        return "\n\n".join(res)

    @tool("create_ticket", args_schema=CreateTicketInput)
    def create_ticket(
        title: str,
        description: str,
        priority: str = "medium",
        category: str = "software",
        user_id: int = 1,
        device_id: Optional[int] = None
    ) -> str:
        """Create a new support ticket when an issue requires human support or tracking."""
        from app.models.user import User
        user = db.query(User).filter_by(id=user_id).first() or db.query(User).first()
        valid_user_id = user.id if user else user_id

        ticket_in = TicketCreate(
            title=title,
            description=description,
            priority=priority,
            category=category,
            user_id=valid_user_id,
            device_id=device_id
        )
        ticket = ticket_repo.create_ticket(ticket_in)
        return json.dumps({
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "title": ticket.title,
            "status": ticket.status,
            "priority": ticket.priority,
            "message": f"Successfully created Ticket #{ticket.ticket_number}"
        })

    @tool("update_ticket", args_schema=UpdateTicketInput)
    def update_ticket(
        ticket_id: int,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """Update an existing ticket's status, priority, title, or description."""
        update_in = TicketUpdate(
            status=status,
            priority=priority,
            title=title,
            description=description
        )
        updated = ticket_repo.update_ticket(ticket_id, update_in)
        if not updated:
            return f"Ticket ID {ticket_id} not found."
        
        return json.dumps({
            "ticket_id": updated.id,
            "ticket_number": updated.ticket_number,
            "status": updated.status,
            "priority": updated.priority,
            "message": f"Successfully updated Ticket #{updated.ticket_number}"
        })

    return [
        search_documents,
        search_tickets,
        get_ticket_history,
        search_error_logs,
        create_ticket,
        update_ticket
    ]
