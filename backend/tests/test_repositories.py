from app.repositories.ticket_repository import TicketRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.error_log_repository import ErrorLogRepository
from app.schemas.ticket import TicketCreate, TicketUpdate
from app.schemas.error_log import ErrorLogCreate


def test_ticket_repository_crud(db_session):
    repo = TicketRepository(db_session)
    
    # Create ticket
    ticket_in = TicketCreate(
        title="VPN Connection Failure",
        description="Gateway timeout when connecting to vpn-east.acme-corp.com",
        priority="high",
        category="network",
        user_id=1
    )
    ticket = repo.create_ticket(ticket_in)
    assert ticket is not None
    assert ticket.ticket_number.startswith("TICK-")
    assert ticket.status == "open"
    assert ticket.title == "VPN Connection Failure"

    # Search ticket
    found = repo.search_tickets(query="VPN")
    assert len(found) == 1
    assert found[0].id == ticket.id

    # Update ticket
    updated = repo.update_ticket(ticket.id, TicketUpdate(status="in_progress", priority="critical"))
    assert updated.status == "in_progress"
    assert updated.priority == "critical"

    # History check
    history = repo.get_history(ticket.id)
    assert len(history) >= 2
    assert history[-1].field_changed == "priority"


def test_error_log_repository(db_session):
    repo = ErrorLogRepository(db_session)
    log_in = ErrorLogCreate(
        service_name="GlobalProtect",
        error_code="ERR_VPN_401",
        log_message="Authentication failed for remote client"
    )
    log = repo.create(log_in)
    assert log.id is not None
    
    results = repo.search_error_logs(query="Authentication")
    assert len(results) == 1
    assert results[0].error_code == "ERR_VPN_401"
