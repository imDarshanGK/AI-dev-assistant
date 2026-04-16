from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_endpoint():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in {307, 308}
    assert response.headers["location"] == "/app/"


def test_frontend_app_endpoint():
    response = client.get("/app/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_docs_disabled_by_default():
    response = client.get("/docs")
    assert response.status_code == 404


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "cache_backend" in body


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


def test_analyze_endpoint_cache_hit_mode():
    payload = {"code": "def add(a, b):\n    return a + b"}
    first = client.post("/analyze/", json=payload)
    assert first.status_code == 200

    second = client.post("/analyze/", json=payload)
    assert second.status_code == 200
    assert second.json()["mode"].endswith("+cache")


def test_versioned_analyze_endpoint():
    payload = {"code": "def add(a, b):\n    return a + b"}
    response = client.post("/api/v1/analyze/", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "provider" in body
    assert "explanation" in body


def test_chat_endpoint_has_rule_based_fallback_response():
    response = client.post(
        "/chat/message",
        json={
            "message": "add two number",
            "history": [],
            "level": "beginner",
            "code": "",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ready+chat_fallback"
    assert "add two numbers" in body["reply"].lower() or "python" in body["reply"].lower()


def test_chat_endpoint_handles_add_2_number_prompt():
    response = client.post(
        "/chat/message",
        json={
            "message": "add 2 number",
            "history": [],
            "level": "beginner",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "result = a + b" in body["reply"].lower()


def test_chat_endpoint_handles_simple_code_prompt():
    response = client.post(
        "/chat/message",
        json={
            "message": "hello give me simple code",
            "history": [],
            "level": "beginner",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "simple python example" in body["reply"].lower()


def test_explanation_summary_is_contextual_for_input_print_code():
    payload = {
        "code": "name = input(\"Enter your name: \")\nprint(\"Hello\", name)",
    }
    response = client.post("/explanation/", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "asks the user for input" in body["summary"].lower()


def test_stream_analyze_endpoint():
    payload = {"code": "def add(a, b):\n    return a + b"}
    response = client.post("/analyze/stream", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: status" in response.text
    assert "event: result" in response.text


def test_websocket_analyze_endpoint():
    with client.websocket_connect("/analyze/ws") as websocket:
        websocket.send_json({"code": "def add(a, b):\n    return a + b"})
        data = websocket.receive_json()
        assert data["explanation"]["language_guess"] == "Python"


def test_share_create_and_get():
    create = client.post(
        "/share/",
        json={
            "action": "analyze",
            "code": "print('hello')",
            "result_json": "{\"status\":\"ok\"}",
        },
    )
    assert create.status_code == 200
    token = create.json()["token"]

    get_result = client.get(f"/share/{token}")
    assert get_result.status_code == 200
    payload = get_result.json()
    assert payload["action"] == "analyze"
    assert payload["code"] == "print('hello')"


def test_validation_error_on_empty_code():
    response = client.post("/explanation/", json={"code": "   "})
    assert response.status_code == 422


def test_validation_error_on_oversized_code():
    oversized = "a" * 20001
    response = client.post("/explanation/", json={"code": oversized})
    assert response.status_code == 422


def test_auth_and_user_data_flow():
    suffix = "testuser_local@example.com"
    signup = client.post("/auth/signup", json={"email": suffix, "password": "StrongPass123"})

    if signup.status_code == 409:
        login = client.post("/auth/login", json={"email": suffix, "password": "StrongPass123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
    else:
        assert signup.status_code == 200
        token = signup.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == suffix

    history_create = client.post(
        "/user/history",
        headers=headers,
        json={
            "action": "analyze",
            "code": "print('hello')",
            "result_json": "{\"status\":\"ok\"}",
        },
    )
    assert history_create.status_code == 200
    history_id = history_create.json()["id"]

    history_list = client.get("/user/history", headers=headers)
    assert history_list.status_code == 200
    assert isinstance(history_list.json(), list)
    assert len(history_list.json()) >= 1

    history_delete = client.delete(f"/user/history/{history_id}", headers=headers)
    assert history_delete.status_code == 200

    history_clear = client.delete("/user/history", headers=headers)
    assert history_clear.status_code == 200

    favorite_create = client.post(
        "/user/favorites",
        headers=headers,
        json={
            "title": "My favorite",
            "action": "analyze",
            "code": "print('hello')",
            "result_json": "{\"status\":\"ok\"}",
        },
    )
    assert favorite_create.status_code == 200
    favorite_id = favorite_create.json()["id"]

    favorite_list = client.get("/user/favorites", headers=headers)
    assert favorite_list.status_code == 200
    assert isinstance(favorite_list.json(), list)
    assert len(favorite_list.json()) >= 1

    favorite_delete = client.delete(f"/user/favorites/{favorite_id}", headers=headers)
    assert favorite_delete.status_code == 200

    favorites_clear = client.delete("/user/favorites", headers=headers)
    assert favorites_clear.status_code == 200
