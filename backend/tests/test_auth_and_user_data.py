import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup path to include the backend directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.main import app

# Use a separate SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_app.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()
    if os.path.exists("./test_app.db"):
        os.remove("./test_app.db")


client = TestClient(app)


def test_auth_and_user_data_flow():
    # 1. Signup
    signup_data = {"email": "contributor@example.com", "password": "securepassword123"}
    r = client.post("/auth/signup", json=signup_data)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    assert data["email"] == "contributor@example.com"
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Login
    login_data = {"email": "contributor@example.com", "password": "securepassword123"}
    r = client.post("/auth/login", json=login_data)
    assert r.status_code == 200
    assert isinstance(r.json()["access_token"], str)
    assert len(r.json()["access_token"]) > 0

    # 3. Get Me
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "contributor@example.com"

    # 4. Create history
    history_payload = {
        "action": "analyze",
        "code": "def hello(): pass",
        "result_json": '{"status": "ok"}',
    }
    r = client.post("/user/history", json=history_payload, headers=headers)
    assert r.status_code == 200
    history_id = r.json()["id"]

    # 5. List history (pagination check)
    r = client.get("/user/history?limit=1", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == history_id

    # 6. Create favorite
    favorite_payload = {
        "title": "My snippet",
        "action": "analyze",
        "code": "def hello(): pass",
        "result_json": '{"status": "ok"}',
    }
    r = client.post("/user/favorites", json=favorite_payload, headers=headers)
    assert r.status_code == 200
    favorite_id = r.json()["id"]

    # 7. List favorites
    r = client.get("/user/favorites", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert r.json()[0]["id"] == favorite_id

    # 8. Delete favorite
    r = client.delete(f"/user/favorites/{favorite_id}", headers=headers)
    assert r.status_code == 200

    # 9. Clear history
    r = client.delete("/user/history", headers=headers)
    assert r.status_code == 200

    r = client.get("/user/history", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 0
