"""
Tests for the /history/ endpoints.
"""
import sys
import os
import tempfile
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import database
from fastapi.testclient import TestClient

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
database.DB_PATH = _tmp.name

asyncio.run(database.init_db())

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TEST_SESSION_LOCAL = sessionmaker(bind=TEST_ENGINE)


def _override_db():
    db = TEST_SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    if previous_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous_override


@pytest.fixture(autouse=True)
def _reset_databases():
    Base.metadata.create_all(bind=TEST_ENGINE)
    if os.path.exists(database.DB_PATH):
        os.remove(database.DB_PATH)
    asyncio.run(database.init_db())
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def auth_headers(client: TestClient, email: str = "history.user@example.com") -> dict[str, str]:
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "StrongPass123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_history_requires_authentication(client):
    assert client.get("/history/").status_code == 401
    assert client.get("/history/search?q=print").status_code == 401
    assert client.post(
        "/history/",
        json={"code": "print('hello')", "language": "Python"},
    ).status_code == 401
    assert client.delete("/history/1").status_code == 401


def test_save_history(client):
    headers = auth_headers(client)
    r = client.post("/history/", json={
        "code": "print('hello')",
        "language": "Python",
        "score": 85,
        "issue_count": 1,
    }, headers=headers)
    assert r.status_code == 201
    d = r.json()
    assert d["status"] == "saved"
    assert "id" in d


def test_get_history(client):
    headers = auth_headers(client)
    client.post(
        "/history/",
        json={"code": "x = 1", "language": "Python", "score": 90, "issue_count": 0},
        headers=headers,
    )
    r = client.get("/history/", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) > 0


def test_get_history_pagination(client):
    headers = auth_headers(client)
    r = client.get("/history/?limit=1&offset=0", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) <= 1


def test_search_history(client):
    headers = auth_headers(client)
    client.post(
        "/history/",
        json={"code": "def my_unique_function(): pass", "language": "Python"},
        headers=headers,
    )
    r = client.get("/history/search?q=my_unique_function", headers=headers)
    assert r.status_code == 200
    results = r.json()
    assert any("my_unique_function" in e["code_preview"] for e in results)


def test_delete_history(client):
    headers = auth_headers(client)
    r = client.post(
        "/history/",
        json={"code": "to be deleted", "language": "Python"},
        headers=headers,
    )
    entry_id = r.json()["id"]
    r = client.delete(f"/history/{entry_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"


def test_delete_nonexistent(client):
    headers = auth_headers(client)
    r = client.delete("/history/999999", headers=headers)
    assert r.status_code == 404


def test_history_entry_fields(client):
    headers = auth_headers(client)
    client.post(
        "/history/",
        json={"code": "let x = 1;", "language": "JavaScript", "score": 70, "issue_count": 2},
        headers=headers,
    )
    r = client.get("/history/", headers=headers)
    assert r.status_code == 200
    entry = r.json()[0]
    assert "id" in entry
    assert "code_hash" in entry
    assert "language" in entry
    assert "score" in entry
    assert "issue_count" in entry
    assert "timestamp" in entry
    assert "code_preview" in entry


def test_search_no_results(client):
    headers = auth_headers(client)
    r = client.get("/history/search?q=xyznotfoundever", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_history_entries_are_scoped_per_user(client):
    alice_headers = auth_headers(client, "alice@example.com")
    bob_headers = auth_headers(client, "bob@example.com")

    alice_save = client.post(
        "/history/",
        json={"code": "print('alice_secret')", "language": "Python"},
        headers=alice_headers,
    )
    assert alice_save.status_code == 201
    alice_entry_id = alice_save.json()["id"]

    bob_save = client.post(
        "/history/",
        json={"code": "print('bob_secret')", "language": "Python"},
        headers=bob_headers,
    )
    assert bob_save.status_code == 201

    bob_history = client.get("/history/", headers=bob_headers)
    assert bob_history.status_code == 200
    assert all("alice_secret" not in entry["code_preview"] for entry in bob_history.json())

    bob_search = client.get("/history/search?q=alice_secret", headers=bob_headers)
    assert bob_search.status_code == 200
    assert bob_search.json() == []

    bob_delete = client.delete(f"/history/{alice_entry_id}", headers=bob_headers)
    assert bob_delete.status_code == 404

    alice_history = client.get("/history/", headers=alice_headers)
    assert any("alice_secret" in entry["code_preview"] for entry in alice_history.json())
