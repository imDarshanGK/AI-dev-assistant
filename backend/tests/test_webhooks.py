from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_webhook():
    payload = {
        "url": "https://example.com/webhook",
        "secret": "test-secret",
    }

    response = client.post(
        "/webhooks/",
        json=payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert "id" in data
    assert data["url"] == payload["url"]
    assert data["enabled"] is True


def test_get_webhooks():
    client.post(
        "/webhooks/",
        json={
            "url": "https://list-test.com/webhook",
            "secret": "secret",
        },
    )

    response = client.get("/webhooks/")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 1


def test_delete_webhook():
    create_response = client.post(
        "/webhooks/",
        json={
            "url": "https://delete-test.com/webhook",
            "secret": "delete-secret",
        },
    )

    webhook_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/webhooks/{webhook_id}"
    )

    assert delete_response.status_code == 200

    assert delete_response.json() == {
        "message": "Webhook deleted"
    }


def test_delete_nonexistent_webhook():
    response = client.delete(
        "/webhooks/999999"
    )

    assert response.status_code == 404

    assert response.json()["detail"] == "Webhook not found"


def test_webhook_test_endpoint():
    with patch(
        "app.routers.webhooks.test_webhook",
        new=AsyncMock(return_value=True),
    ):
        response = client.post(
            "/webhooks/test",
            json={
                "url": "https://example.com/webhook",
                "secret": "test-secret",
            },
        )

        assert response.status_code == 200

        assert response.json() == {
            "success": True
        }


def test_webhook_test_endpoint_failure():
    with patch(
        "app.routers.webhooks.test_webhook",
        new=AsyncMock(return_value=False),
    ):
        response = client.post(
            "/webhooks/test",
            json={
                "url": "https://example.com/webhook",
                "secret": "test-secret",
            },
        )

        assert response.status_code == 200

        assert response.json() == {
            "success": False
        }


def test_create_signature():
    from app.services.webhook_service import create_signature

    payload = {
        "event": "analysis.completed"
    }

    signature = create_signature(
        payload,
        "secret-key",
    )

    assert isinstance(signature, str)

    # sha256 hex digest length
    assert len(signature) == 64


def test_create_signature_is_deterministic():
    from app.services.webhook_service import create_signature

    payload = {
        "event": "analysis.completed"
    }

    sig1 = create_signature(
        payload,
        "secret-key",
    )

    sig2 = create_signature(
        payload,
        "secret-key",
    )

    assert sig1 == sig2