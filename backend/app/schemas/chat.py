from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ToolCallDetail(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result_summary: str


class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: List[ChatMessage] = []
    user_id: Optional[int] = 1
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str
    tools_used: List[ToolCallDetail] = []
    ticket_created: Optional[Dict[str, Any]] = None
    ticket_updated: Optional[Dict[str, Any]] = None
    rag_sources: List[Dict[str, Any]] = []
    sql_sources: List[Dict[str, Any]] = []
