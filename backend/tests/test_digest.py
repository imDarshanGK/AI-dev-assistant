"""
Tests for weekly email digest — subscribe / unsubscribe / scheduler.
Run: cd backend && pytest test_digest.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.models import DigestSubscription

# Now import the FastAPI app and wire up the test DB override.
from app.main import app as fastapi_app


from sqlalchemy.pool import StaticPool
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


fastapi_app.dependency_overrides[get_db] = _override_db
client = TestClient(fastapi_app)


# ── Setup / Teardown ──────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _recreate_tables():
    """Recreate all tables before each test for a clean slate."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


# ── Tests ─────────────────────────────────────────────────────────────────────
def test_subscribe_success():
    r = client.post("/subscribe/", json={"email": "test@example.com"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "test@example.com"
    assert "subscribed" in data["message"].lower()


def test_subscribe_duplicate_returns_409():
    client.post("/subscribe/", json={"email": "test@example.com"})
    r = client.post("/subscribe/", json={"email": "test@example.com"})
    assert r.status_code == 409
    assert "already subscribed" in r.json()["detail"].lower()


def test_subscribe_re_activates_after_unsubscribe():
    client.post("/subscribe/", json={"email": "test@example.com"})

    db = TEST_SESSION_LOCAL()
    try:
        sub = db.query(DigestSubscription).filter(
            DigestSubscription.email == "test@example.com"
        ).first()
        token = sub.unsubscribe_token
    finally:
        db.close()

    r = client.post("/subscribe/unsubscribe", json={
        "email": "test@example.com", "token": token
    })
    assert r.status_code == 200

    r = client.post("/subscribe/", json={"email": "test@example.com"})
    assert r.status_code == 200
    assert "re-activated" in r.json()["message"].lower()


def test_unsubscribe_success():
    client.post("/subscribe/", json={"email": "test@example.com"})
    db = TEST_SESSION_LOCAL()
    try:
        sub = db.query(DigestSubscription).filter(
            DigestSubscription.email == "test@example.com"
        ).first()
        token = sub.unsubscribe_token
    finally:
        db.close()

    r = client.post("/subscribe/unsubscribe", json={
        "email": "test@example.com", "token": token
    })
    assert r.status_code == 200
    assert "unsubscribed" in r.json()["message"].lower()


def test_unsubscribe_wrong_token():
    client.post("/subscribe/", json={"email": "test@example.com"})
    r = client.post("/subscribe/unsubscribe", json={
        "email": "test@example.com", "token": "wrong-token"
    })
    assert r.status_code == 403


def test_unsubscribe_nonexistent():
    r = client.post("/subscribe/unsubscribe", json={
        "email": "nobody@example.com", "token": "some-token"
    })
    assert r.status_code == 404


def test_get_unsubscribe_link():
    client.post("/subscribe/", json={"email": "test@example.com"})
    db = TEST_SESSION_LOCAL()
    try:
        sub = db.query(DigestSubscription).filter(
            DigestSubscription.email == "test@example.com"
        ).first()
        token = sub.unsubscribe_token
    finally:
        db.close()

    r = client.get("/subscribe/unsubscribe", params={
        "email": "test@example.com", "token": token
    })
    assert r.status_code == 200
    assert "unsubscribed" in r.json()["message"].lower()


def test_invalid_email():
    r = client.post("/subscribe/", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_subscribe_stores_token():
    client.post("/subscribe/", json={"email": "token-test@example.com"})
    db = TEST_SESSION_LOCAL()
    try:
        sub = db.query(DigestSubscription).filter(
            DigestSubscription.email == "token-test@example.com"
        ).first()
        assert sub is not None
        assert sub.is_active is True
        assert len(sub.unsubscribe_token) >= 16
    finally:
        db.close()
