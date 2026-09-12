from typing import Dict, List
from pydantic import BaseModel


class StatusCount(BaseModel):
    status: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class PriorityCount(BaseModel):
    priority: str
    count: int


class DailyCount(BaseModel):
    date: str
    count: int


class ErrorCodeCount(BaseModel):
    error_code: str
    count: int


class CategoryResolution(BaseModel):
    category: str
    total: int
    resolved: int
    rate: float


class KnowledgeUsage(BaseModel):
    total_documents: int
    total_chunks: int
    embedded_chunks: int
    embedding_coverage: float
    documents_by_category: List[CategoryCount]


class AnalyticsSummary(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    escalated_tickets: int
    total_incidents: int
    total_devices: int
    total_knowledge_docs: int
    tickets_by_status: List[StatusCount]
    tickets_by_category: List[CategoryCount]
    tickets_by_priority: List[PriorityCount]
    ai_resolution_rate: float


class AnalyticsDashboard(BaseModel):
    """Full analytics payload powering the dashboard charts."""
    summary: AnalyticsSummary
    tickets_by_priority: List[PriorityCount]
    tickets_by_category: List[CategoryCount]
    daily_trend: List[DailyCount]
    avg_resolution_time_hours: float
    top_recurring_errors: List[ErrorCodeCount]
    knowledge_usage: KnowledgeUsage
    resolution_rate_by_category: List[CategoryResolution]
