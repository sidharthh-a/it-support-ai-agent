from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    tools_used: List[Dict[str, Any]]
    ticket_created: Optional[Dict[str, Any]]
    ticket_updated: Optional[Dict[str, Any]]
    rag_sources: List[Dict[str, Any]]
    sql_sources: List[Dict[str, Any]]
