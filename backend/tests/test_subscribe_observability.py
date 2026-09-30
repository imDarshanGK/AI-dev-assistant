"""Tests verifying that subscribe router increments observability counters."""

from __future__ import annotations

import pytest
from app import observability
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import DigestSubscription
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── In-memory test database setup ─────────────────────────────────────────────

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


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(TEST_ENGINE)
    fastapi_app.dependency_overrides[get_db] = _override_db
    yield
    fastapi_app.dependency_overrides.clear()
    Base.metadata.drop_all(TEST_ENGINE)


client = TestClient(fastapi_app)


# ── Helper ────────────────────────────────────────────────────────────────────


def _get_token(email: str) -> str:
    client.post("/subscribe/", json={"email": email})
    db = TEST_SESSION_LOCAL()
    try:
        sub = (
            db.query(DigestSubscription)
            .filter(DigestSubscription.email == email.lower())
            .first()
        )
        return sub.unsubscribe_token
    finally:
        db.close()


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


# ── Subscribe POST observability ──────────────────────────────────────────────


def test_subscribe_success_increments_counter():
    before = _counter_value(observability.SUBSCRIBE_ATTEMPTS_TOTAL, result="success")
    client.post("/subscribe/", json={"email": "obs_success@example.com"})
    after = _counter_value(observability.SUBSCRIBE_ATTEMPTS_TOTAL, result="success")
    assert after == before + 1


def test_subscribe_duplicate_increments_counter():
    email = "obs_duplicate@example.com"
    client.post("/subscribe/", json={"email": email})

    before = _counter_value(observability.SUBSCRIBE_ATTEMPTS_TOTAL, result="duplicate")
    client.post("/subscribe/", json={"email": email})
    after = _counter_value(observability.SUBSCRIBE_ATTEMPTS_TOTAL, result="duplicate")
    assert after == before + 1


def test_subscribe_reactivated_increments_counter():
    email = "obs_reactivate@example.com"
    token = _get_token(email)
    client.post("/subscribe/unsubscribe", json={"email": email, "token": token})

    before = _counter_value(
        observability.SUBSCRIBE_ATTEMPTS_TOTAL, result="reactivated"
    )
    client.post("/subscribe/", json={"email": email})
    after = _counter_value(observability.SUBSCRIBE_ATTEMPTS_TOTAL, result="reactivated")
    assert after == before + 1


# ── Unsubscribe POST observability ────────────────────────────────────────────


def test_unsubscribe_post_success_increments_counter():
    email = "obs_unsub_success@example.com"
    token = _get_token(email)

    before = _counter_value(
        observability.UNSUBSCRIBE_POST_ATTEMPTS_TOTAL, result="success"
    )
    client.post("/subscribe/unsubscribe", json={"email": email, "token": token})
    after = _counter_value(
        observability.UNSUBSCRIBE_POST_ATTEMPTS_TOTAL, result="success"
    )
    assert after == before + 1


def test_unsubscribe_post_not_found_increments_counter():
    before = _counter_value(
        observability.UNSUBSCRIBE_POST_ATTEMPTS_TOTAL, result="not_found"
    )
    client.post(
        "/subscribe/unsubscribe",
        json={"email": "ghost@example.com", "token": "anytoken"},
    )
    after = _counter_value(
        observability.UNSUBSCRIBE_POST_ATTEMPTS_TOTAL, result="not_found"
    )
    assert after == before + 1


def test_unsubscribe_post_invalid_token_increments_counter():
    email = "obs_wrong_token@example.com"
    client.post("/subscribe/", json={"email": email})

    before = _counter_value(
        observability.UNSUBSCRIBE_POST_ATTEMPTS_TOTAL, result="invalid_token"
    )
    client.post(
        "/subscribe/unsubscribe",
        json={"email": email, "token": "wrongtoken"},
    )
    after = _counter_value(
        observability.UNSUBSCRIBE_POST_ATTEMPTS_TOTAL, result="invalid_token"
    )
    assert after == before + 1


# ── Unsubscribe GET observability ─────────────────────────────────────────────


def test_unsubscribe_get_success_increments_counter():
    email = "obs_get_success@example.com"
    token = _get_token(email)

    before = _counter_value(
        observability.UNSUBSCRIBE_GET_ATTEMPTS_TOTAL, result="success"
    )
    client.get(f"/subscribe/unsubscribe?email={email}&token={token}")
    after = _counter_value(
        observability.UNSUBSCRIBE_GET_ATTEMPTS_TOTAL, result="success"
    )
    assert after == before + 1


def test_unsubscribe_get_not_found_increments_counter():
    before = _counter_value(
        observability.UNSUBSCRIBE_GET_ATTEMPTS_TOTAL, result="not_found"
    )
    client.get("/subscribe/unsubscribe?email=ghost@example.com&token=any")
    after = _counter_value(
        observability.UNSUBSCRIBE_GET_ATTEMPTS_TOTAL, result="not_found"
    )
    assert after == before + 1


def test_unsubscribe_get_invalid_token_increments_counter():
    email = "obs_get_wrong_token@example.com"
    client.post("/subscribe/", json={"email": email})

    before = _counter_value(
        observability.UNSUBSCRIBE_GET_ATTEMPTS_TOTAL, result="invalid_token"
    )
    client.get(f"/subscribe/unsubscribe?email={email}&token=wrongtoken")
    after = _counter_value(
        observability.UNSUBSCRIBE_GET_ATTEMPTS_TOTAL, result="invalid_token"
    )
    assert after == before + 1
