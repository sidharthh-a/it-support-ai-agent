from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from app.models.error_log import ErrorLog
from app.schemas.error_log import ErrorLogCreate


class ErrorLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def search_error_logs(
        self,
        query: Optional[str] = None,
        service_name: Optional[str] = None,
        error_code: Optional[str] = None,
        device_id: Optional[int] = None,
        limit: int = 50
    ) -> List[ErrorLog]:
        stmt = select(ErrorLog)
        filters = []

        if query:
            pattern = f"%{query}%"
            filters.append(
                or_(
                    ErrorLog.log_message.ilike(pattern),
                    ErrorLog.error_code.ilike(pattern),
                    ErrorLog.service_name.ilike(pattern),
                    ErrorLog.stack_trace.ilike(pattern)
                )
            )
        if service_name:
            filters.append(ErrorLog.service_name == service_name)
        if error_code:
            filters.append(ErrorLog.error_code == error_code)
        if device_id:
            filters.append(ErrorLog.device_id == device_id)

        if filters:
            stmt = stmt.where(*filters)

        stmt = stmt.order_by(ErrorLog.timestamp.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, log_in: ErrorLogCreate) -> ErrorLog:
        log = ErrorLog(
            device_id=log_in.device_id,
            ticket_id=log_in.ticket_id,
            service_name=log_in.service_name,
            error_code=log_in.error_code,
            log_message=log_in.log_message,
            stack_trace=log_in.stack_trace
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
