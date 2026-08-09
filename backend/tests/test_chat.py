from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_chat_endpoint_uses_context_in_fallback_response():
    response = client.post(
        "/chat/",
        json={
            "message": "How do I fix this?",
            "code": "def divide(a, b):\n    return a / b\n",
            "context": "This code divides by a runtime value and may fail with ZeroDivisionError.",
            "history": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "response" in body
    assert "division" in body["response"].lower() or "zerodivision" in body["response"].lower()
