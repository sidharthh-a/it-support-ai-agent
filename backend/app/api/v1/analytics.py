from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analytics import (
    AnalyticsDashboard,
    AnalyticsSummary,
    CategoryCount,
    CategoryResolution,
    DailyCount,
    ErrorCodeCount,
    KnowledgeUsage,
    PriorityCount,
    StatusCount,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/", response_model=AnalyticsSummary)
def get_analytics_summary(db: Session = Depends(get_db)):
    svc = AnalyticsService(db)
    s = svc.summary()
    return AnalyticsSummary(
        **s,
        tickets_by_status=[StatusCount(**x) for x in svc.tickets_by_status()],
        tickets_by_category=[CategoryCount(**x) for x in svc.tickets_by_category()],
        tickets_by_priority=[PriorityCount(**x) for x in svc.tickets_by_priority()],
    )


@router.get("/dashboard", response_model=AnalyticsDashboard)
def get_analytics_dashboard(
    days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
):
    """All dashboard charts in one call — every value SQL-aggregated from the database."""
    svc = AnalyticsService(db)
    s = svc.summary()
    return AnalyticsDashboard(
        summary=AnalyticsSummary(
            **s,
            tickets_by_status=[StatusCount(**x) for x in svc.tickets_by_status()],
            tickets_by_category=[CategoryCount(**x) for x in svc.tickets_by_category()],
            tickets_by_priority=[PriorityCount(**x) for x in svc.tickets_by_priority()],
        ),
        tickets_by_priority=[PriorityCount(**x) for x in svc.tickets_by_priority()],
        tickets_by_category=[CategoryCount(**x) for x in svc.tickets_by_category()],
        daily_trend=[DailyCount(**x) for x in svc.daily_trend(days=days)],
        avg_resolution_time_hours=svc.avg_resolution_time_hours(),
        top_recurring_errors=[ErrorCodeCount(**x) for x in svc.top_recurring_errors()],
        knowledge_usage=KnowledgeUsage(**svc.knowledge_usage()),
        resolution_rate_by_category=[CategoryResolution(**x) for x in svc.resolution_rate_by_category()],
    )
