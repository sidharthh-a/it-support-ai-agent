import pytest


def test_chat_agent_endpoint(client):
    payload = {
        "message": "How do I fix VPN connection timeout issue?"
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 0


def test_chat_agent_create_ticket_intent(client):
    payload = {
        "message": "Please create ticket: My monitor is displaying green lines and flickering violently."
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ticket_created"] is not None
    assert data["ticket_created"]["ticket_number"].startswith("TICK-")


@pytest.mark.parametrize("greeting", ["hey", "hello", "hi", "thanks", "good morning", "Good afternoon!"])
def test_greeting_casual_queries_no_tools(client, greeting):
    """Greeting/casual queries must return concise response without calling tools."""
    payload = {"message": greeting}
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Hey! How can I help you with an IT issue?" in data["answer"]
    assert data["tools_used"] == []
    assert data["rag_sources"] == []
    assert data["sql_sources"] == []

