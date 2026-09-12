import json
from app.tools.agent_tools import create_agent_tools


def test_agent_tools_execution(db_session):
    tools = create_agent_tools(db_session)
    tool_map = {t.name: t for t in tools}

    assert "search_documents" in tool_map
    assert "search_tickets" in tool_map
    assert "get_ticket_history" in tool_map
    assert "search_error_logs" in tool_map
    assert "create_ticket" in tool_map
    assert "update_ticket" in tool_map

    # Test create_ticket tool
    res = tool_map["create_ticket"].invoke({
        "title": "Wi-Fi Authentication Issue",
        "description": "Unable to log in to 802.1X network",
        "priority": "high",
        "category": "network",
        "user_id": 1
    })
    data = json.loads(res)
    assert data["ticket_number"].startswith("TICK-")
    assert data["status"] == "open"

    # Test search_tickets tool
    search_res = tool_map["search_tickets"].invoke({"query": "Wi-Fi"})
    assert "Wi-Fi Authentication Issue" in search_res
