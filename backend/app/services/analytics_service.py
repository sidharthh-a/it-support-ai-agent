"""Analytics service — every metric computed with SQL aggregation over the database.

The database is the single source of truth; no hardcoded analytics values.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import func, select, case, desc
from sqlalchemy.orm import Session

from app.models.ticket import SupportTicket
from app.models.error_log import ErrorLog
from app.models.knowledge import KnowledgeDocument, DocumentChunk
from app.models.incident import Incident
from app.models.device import Device


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def summary(self) -> Dict[str, Any]:
        """Headline KPI block (existing AnalyticsSummary fields, SQL-computed)."""
        total_tickets = self.db.scalar(select(func.count(SupportTicket.id))) or 0
        open_tickets = self.db.scalar(select(func.count(SupportTicket.id)).where(SupportTicket.status == "open")) or 0
        in_progress = self.db.scalar(select(func.count(SupportTicket.id)).where(SupportTicket.status == "in_progress")) or 0
        resolved = self.db.scalar(select(func.count(SupportTicket.id)).where(SupportTicket.status == "resolved")) or 0
        escalated = self.db.scalar(select(func.count(SupportTicket.id)).where(SupportTicket.status == "escalated")) or 0

        return {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "in_progress_tickets": in_progress,
            "resolved_tickets": resolved,
            "escalated_tickets": escalated,
            "total_incidents": self.db.scalar(select(func.count(Incident.id))) or 0,
            "total_devices": self.db.scalar(select(func.count(Device.id))) or 0,
            "total_knowledge_docs": self.db.scalar(select(func.count(KnowledgeDocument.id))) or 0,
            "ai_resolution_rate": round((resolved / max(total_tickets, 1)) * 100, 1),
        }

    def tickets_by_priority(self) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            select(SupportTicket.priority, func.count(SupportTicket.id)).group_by(SupportTicket.priority)
        ).all()
        return [{"priority": p, "count": c} for p, c in rows]

    def tickets_by_category(self) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            select(SupportTicket.category, func.count(SupportTicket.id)).group_by(SupportTicket.category)
        ).all()
        return [{"category": c, "count": n} for c, n in rows]

    def tickets_by_status(self) -> List[Dict[str, Any]]:
        rows = self.db.execute(
            select(SupportTicket.status, func.count(SupportTicket.id)).group_by(SupportTicket.status)
        ).all()
        return [{"status": s, "count": c} for s, c in rows]

    def daily_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """Ticket creation counts per day for the last N days (SQL date_trunc / date arithmetic)."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        date_expr = func.date(SupportTicket.created_at).label("day")
        rows = self.db.execute(
            select(date_expr, func.count(SupportTicket.id))
            .where(SupportTicket.created_at >= since)
            .group_by(date_expr)
            .order_by(date_expr)
        ).all()
        return [{"date": d.isoformat() if hasattr(d, "isoformat") else str(d), "count": c} for d, c in rows]

    def avg_resolution_time_hours(self) -> float:
        """Average hours between ticket creation and its resolution timestamp (SQL AVG)."""
        from app.models.resolution import Resolution
        seconds = self.db.execute(
            select(func.avg(
                func.extract("epoch", Resolution.resolved_at) - func.extract("epoch", SupportTicket.created_at)
            )).join(SupportTicket, Resolution.ticket_id == SupportTicket.id)
        ).scalar()
        if seconds is None:
            return 0.0
        return round(float(seconds) / 3600.0, 1)

    def top_recurring_errors(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Most frequent error codes across system logs (SQL GROUP BY + ORDER BY count)."""
        rows = self.db.execute(
            select(ErrorLog.error_code, func.count(ErrorLog.id).label("occurrences"))
            .group_by(ErrorLog.error_code)
            .order_by(desc("occurrences"))
            .limit(limit)
        ).all()
        return [{"error_code": code, "count": c} for code, c in rows]

    def knowledge_usage(self) -> Dict[str, Any]:
        """Knowledge-base coverage metrics: docs, chunks, embedded chunks, per-category docs."""
        total_docs = self.db.scalar(select(func.count(KnowledgeDocument.id))) or 0
        total_chunks = self.db.scalar(select(func.count(DocumentChunk.id))) or 0
        embedded = self.db.scalar(select(func.count(DocumentChunk.id)).where(DocumentChunk.embedding.isnot(None))) or 0
        by_category_rows = self.db.execute(
            select(KnowledgeDocument.category, func.count(KnowledgeDocument.id))
            .group_by(KnowledgeDocument.category)
        ).all()
        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "embedded_chunks": embedded,
            "embedding_coverage": round(embedded / total_chunks * 100, 1) if total_chunks else 0.0,
            "documents_by_category": [{"category": c, "count": n} for c, n in by_category_rows],
        }

    def resolution_rate_by_category(self) -> List[Dict[str, Any]]:
        """Resolved vs total per category (SQL conditional aggregation)."""
        rows = self.db.execute(
            select(
                SupportTicket.category,
                func.count(SupportTicket.id).label("total"),
                func.sum(case((SupportTicket.status == "resolved", 1), else_=0)).label("resolved"),
            ).group_by(SupportTicket.category)
        ).all()
        return [
            {
                "category": c,
                "total": t,
                "resolved": int(r or 0),
                "rate": round((float(r or 0) / t) * 100, 1) if t else 0.0,
            }
            for c, t, r in rows
        ]
