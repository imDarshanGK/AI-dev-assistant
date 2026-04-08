from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "message" in body
    assert body["docs"] == "/docs"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_id_header_present():
    response = client.get("/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_explanation_endpoint():
    payload = {"code": "def add(a, b):\n    return a + b"}
    response = client.post("/explanation/", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["language_guess"] == "Python"
    assert isinstance(body["key_points"], list)


def test_debugging_endpoint_syntax_error():
    payload = {"code": "def broken_func(\n    return 1"}
    response = client.post("/debugging/", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["issues"], list)
    assert len(body["issues"]) >= 1


def test_suggestions_endpoint():
    payload = {"code": "x=1\nprint(x)"}
    response = client.post("/suggestions/", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["language_guess"] == "Python"
    assert len(body["suggestions"]) >= 1


def test_analyze_endpoint():
    payload = {"code": "def add(a, b):\n    return a + b"}
    response = client.post("/analyze/", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "rule-based"
    assert body["mode"] == "ready"
    assert body["explanation"]["language_guess"] == "Python"
    assert isinstance(body["debugging"]["issues"], list)
    assert isinstance(body["suggestions"]["suggestions"], list)


def test_validation_error_on_empty_code():
    response = client.post("/explanation/", json={"code": "   "})
    assert response.status_code == 422


def test_validation_error_on_oversized_code():
    oversized = "a" * 20001
    response = client.post("/explanation/", json={"code": oversized})
    assert response.status_code == 422
