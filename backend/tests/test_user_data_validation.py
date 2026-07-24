from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_validation.db"
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
    if os.path.exists("./test_validation.db"):
        os.remove("./test_validation.db")


client = TestClient(app)


def test_delete_history_invalid_ids():
    signup_data = {
        "email": "validation_user@example.com",
        "password": "securepassword123",
    }
    r = client.post("/auth/signup", json=signup_data)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.delete("/user/history/-5", headers=headers)
    assert r.status_code == 422

    r = client.delete("/user/history/0", headers=headers)
    assert r.status_code == 422

    r = client.delete("/user/history/9999", headers=headers)
    assert r.status_code == 404


def test_delete_favorite_invalid_ids():
    signup_data = {
        "email": "validation_user2@example.com",
        "password": "securepassword123",
    }
    r = client.post("/auth/signup", json=signup_data)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.delete("/user/favorites/-3", headers=headers)
    assert r.status_code == 422

    r = client.delete("/user/favorites/0", headers=headers)
    assert r.status_code == 422

    r = client.delete("/user/favorites/9999", headers=headers)
    assert r.status_code == 404
