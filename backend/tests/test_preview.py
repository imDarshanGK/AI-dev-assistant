from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ADMIN_TOKEN = "admin-secret-token"


def test_preview_basic():
    """Template renders correctly with all variables supplied."""
    response = client.post("/admin/preview/", json={
        "template": "Analyze {language} code: {code}",
        "variables": {"language": "Python", "code": "x = 1"},
        "admin_token": ADMIN_TOKEN,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["rendered_prompt"] == "Analyze Python code: x = 1"
    assert "language" in data["variables_found"]
    assert data["variables_missing"] == []


def test_preview_missing_variable():
    """Reports missing placeholders when variable not supplied."""
    response = client.post("/admin/preview/", json={
        "template": "Hello {name}, analyze {code}",
        "variables": {"name": "Admin"},
        "admin_token": ADMIN_TOKEN,
    })
    assert response.status_code == 200
    data = response.json()
    assert "code" in data["variables_missing"]


def test_preview_with_mock_response():
    """Returns a mock provider response when requested."""
    response = client.post("/admin/preview/", json={
        "template": "Check this: {code}",
        "variables": {"code": "print('hi')"},
        "mock_response": True,
        "admin_token": ADMIN_TOKEN,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["mock_provider_response"] is not None
    assert "[MOCK RESPONSE]" in data["mock_provider_response"]


def test_preview_unauthorized():
    """Rejects requests without valid admin token."""
    response = client.post("/admin/preview/", json={
        "template": "Hello {name}",
        "variables": {"name": "test"},
        "admin_token": "wrong-token",
    })
    assert response.status_code == 403
