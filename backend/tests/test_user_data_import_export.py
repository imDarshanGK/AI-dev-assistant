"""Integration tests for user data import/export endpoints"""

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.main import app as fastapi_app

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
    previous_override = fastapi_app.dependency_overrides.get(get_db)
    fastapi_app.dependency_overrides[get_db] = _override_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    if previous_override is None:
        fastapi_app.dependency_overrides.pop(get_db, None)
    else:
        fastapi_app.dependency_overrides[get_db] = previous_override


@pytest.fixture(autouse=True)
def _recreate_tables():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def test_import_export_user_data_flow(client):
    # 1. Sign up and log in user
    signup_response = client.post(
        "/auth/signup",
        json={"email": "tester@example.com", "password": "StrongPass123!"},
    )
    assert signup_response.status_code == 200
    token = signup_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Export initially (should be empty)
    export_response = client.get("/user/export", headers=headers)
    assert export_response.status_code == 200
    data = export_response.json()
    assert data["history"] == []
    assert data["favorites"] == []

    # 3. Import some user data
    import_payload = {
        "history": [
            {
                "action": "explain",
                "code": "print('hello')",
                "result_json": '{"status": "ok"}'
            },
            {
                "action": "debug",
                "code": "def func(): pass",
                "result_json": '{"errors": []}'
            }
        ],
        "favorites": [
            {
                "title": "My Favorite Code",
                "action": "explain",
                "code": "x = 10",
                "result_json": '{"explanation": "Sets variable x to 10"}'
            }
        ]
    }
    import_response = client.post("/user/import", json=import_payload, headers=headers)
    assert import_response.status_code == 200
    import_result = import_response.json()
    assert import_result["status"] == "success"
    assert import_result["imported_history_count"] == 2
    assert import_result["imported_favorites_count"] == 1

    # 4. Export again and verify imported entries are returned
    export_response = client.get("/user/export", headers=headers)
    assert export_response.status_code == 200
    data = export_response.json()
    
    assert len(data["history"]) == 2
    assert data["history"][0]["action"] == "explain"
    assert data["history"][0]["code"] == "print('hello')"
    assert data["history"][0]["result_json"] == '{"status": "ok"}'
    
    assert data["history"][1]["action"] == "debug"
    assert data["history"][1]["code"] == "def func(): pass"
    assert data["history"][1]["result_json"] == '{"errors": []}'

    assert len(data["favorites"]) == 1
    assert data["favorites"][0]["title"] == "My Favorite Code"
    assert data["favorites"][0]["action"] == "explain"
    assert data["favorites"][0]["code"] == "x = 10"
    assert data["favorites"][0]["result_json"] == '{"explanation": "Sets variable x to 10"}'


def test_import_validation_failures(client):
    signup_response = client.post(
        "/auth/signup",
        json={"email": "tester2@example.com", "password": "StrongPass123!"},
    )
    assert signup_response.status_code == 200
    token = signup_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Action too short (should trigger pydantic min_length=3 validator validation error)
    bad_payload = {
        "history": [
            {
                "action": "ex",
                "code": "print('hello')",
                "result_json": '{"status": "ok"}'
            }
        ]
    }
    response = client.post("/user/import", json=bad_payload, headers=headers)
    assert response.status_code == 422
