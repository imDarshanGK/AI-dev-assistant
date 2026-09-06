import logging
import uuid

from app.main import app
from fastapi.testclient import TestClient


def test_request_id_propagates_to_response_and_logs(caplog):
    client = TestClient(app)
    try:
        with caplog.at_level(logging.INFO, logger="ai_assistant.api"):
            response = client.get("/ping")
    finally:
        client.close()

    request_id = response.headers["X-Request-ID"]
    assert str(uuid.UUID(request_id)) == request_id

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        f"request_started request_id={request_id}" in message for message in messages
    )
    assert any(
        f"request_finished request_id={request_id}" in message for message in messages
    )
