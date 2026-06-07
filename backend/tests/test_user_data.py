import pytest
from app.models import QueryHistory, FavoriteResult

# ==============================================================================
# HISTORY ENDPOINT TESTS (/user/history)
# ==============================================================================

def test_create_history_success(client):
    payload = {
        "action": "explain",
        "code": "def hello(): print('world')",
        "result_json": {"summary": "Prints world"}
    }
    response = client.post("/user/history", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == payload["action"]
    assert data["code"] == payload["code"]
    assert data["result_json"] == payload["result_json"]
    assert "id" in data
    assert "created_at" in data

def test_list_history_returns_records(client, db_session, mock_user):
    # Setup some pre-existing history records
    history_item = QueryHistory(
        user_id=mock_user.id,
        action="debug",
        code="int x = 0;",
        result_json={"issues": []}
    )
    db_session.add(history_item)
    db_session.commit()

    response = client.get("/user/history")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["code"] == "int x = 0;"

def test_history_hardcoded_pagination_limit(client, db_session, mock_user):
    # Populate database with more than the 50-limit threshold (e.g., 55 items)
    items = [
        QueryHistory(
            user_id=mock_user.id,
            action="suggest",
            code=f"// code block {i}",
            result_json={}
        ) for i in range(55)
    ]
    db_session.add_all(items)
    db_session.commit()

    response = client.get("/user/history")
    assert response.status_code == 200
    data = response.json()
    # Confirm maximum threshold is enforced
    assert len(data) == 50
    # Confirm descending sort strategy (last inserted item first)
    assert data[0]["code"] == "// code block 54"

def test_delete_individual_history_record(client, db_session, mock_user):
    history_item = QueryHistory(user_id=mock_user.id, action="test", code="pass", result_json={})
    db_session.add(history_item)
    db_session.commit()
    db_session.refresh(history_item)

    # Delete existing item
    response = client.delete(f"/user/history/{history_item.id}")
    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "history_id": history_item.id}

    # Verify 404 behavior upon subsequent lookup calls
    response_404 = client.delete(f"/user/history/{history_item.id}")
    assert response_404.status_code == 404

def test_clear_all_history_records(client, db_session, mock_user):
    items = [
        QueryHistory(user_id=mock_user.id, action="test", code="pass", result_json={}),
        QueryHistory(user_id=mock_user.id, action="test2", code="pass2", result_json={})
    ]
    db_session.add_all(items)
    db_session.commit()

    response = client.delete("/user/history")
    assert response.status_code == 200
    assert response.json() == {"status": "cleared", "deleted": 2}

    # Verify list is empty
    assert len(client.get("/user/history").json()) == 0


# ==============================================================================
# FAVORITES ENDPOINT TESTS (/user/favorites)
# ==============================================================================

def test_create_favorite_success(client):
    payload = {
        "title": "Optimized Sort",
        "action": "suggest",
        "code": "void sort() {}",
        "result_json": {"grade": "A"}
    }
    response = client.post("/user/favorites", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["code"] == payload["code"]
    assert "id" in data

def test_list_favorites_returns_records(client, db_session, mock_user):
    fav_item = FavoriteResult(
        user_id=mock_user.id,
        title="My Fav",
        action="explain",
        code="print()",
        result_json={}
    )
    db_session.add(fav_item)
    db_session.commit()

    response = client.get("/user/favorites")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "My Fav"

def test_favorites_hardcoded_pagination_limit(client, db_session, mock_user):
    items = [
        FavoriteResult(
            user_id=mock_user.id,
            title=f"Fav {i}",
            action="explain",
            code="code",
            result_json={}
        ) for i in range(52)
    ]
    db_session.add_all(items)
    db_session.commit()

    response = client.get("/user/favorites")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 50
    assert data[0]["title"] == "Fav 51"

def test_delete_individual_favorite_record(client, db_session, mock_user):
    fav_item = FavoriteResult(user_id=mock_user.id, title="Del Me", action="debug", code="x=1", result_json={})
    db_session.add(fav_item)
    db_session.commit()
    db_session.refresh(fav_item)

    response = client.delete(f"/user/favorites/{fav_item.id}")
    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "favorite_id": fav_item.id}

    # Verify 404 behavior
    assert client.delete(f"/user/favorites/{fav_item.id}").status_code == 404

def test_clear_all_favorites_records(client, db_session, mock_user):
    items = [
        FavoriteResult(user_id=mock_user.id, title="F1", action="a", code="c", result_json={}),
        FavoriteResult(user_id=mock_user.id, title="F2", action="a", code="c", result_json={})
    ]
    db_session.add_all(items)
    db_session.commit()

    response = client.delete("/user/favorites")
    assert response.status_code == 200
    assert response.json() == {"status": "cleared", "deleted": 2}


# ==============================================================================
# SECURITY / PERMISSION REJECTION TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "method, endpoint, payload",
    [
        ("GET", "/user/history", None),
        ("POST", "/user/history", {"action": "test", "code": "pass", "result_json": {}}),
        ("DELETE", "/user/history", None),
        ("DELETE", "/user/history/1", None),
        ("GET", "/user/favorites", None),
        ("POST", "/user/favorites", {"title": "T", "action": "A", "code": "C", "result_json": {}}),
        ("DELETE", "/user/favorites", None),
        ("DELETE", "/user/favorites/1", None),
    ],
)
def test_endpoints_raise_411_unauthorized_when_no_token_present(unauthenticated_client, method, endpoint, payload):
    """Ensures unauthorized operations fail appropriately across all target user endpoints."""
    if method == "GET":
        response = unauthenticated_client.get(endpoint)
    elif method == "POST":
        response = unauthenticated_client.post(endpoint, json=payload)
    elif method == "DELETE":
        response = unauthenticated_client.delete(endpoint)
        
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"