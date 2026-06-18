"""Tests for AI usage tracking, cost summaries, and quota enforcement."""

from datetime import UTC, datetime, timedelta
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
from app.main import _request_counts
from app.models import QuotaConfig, UsageLog
from app.services.cache import cache
from app.services.usage import (
    UsageEstimate,
    aggregate_usage,
    build_alerts,
    enforce_quota,
    estimate_tokens,
    estimate_usage,
    parse_thresholds,
    provider_costs,
)


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
    cache.clear_memory()
    _request_counts.clear()
    with TestClient(fastapi_app) as test_client:
        yield test_client
    cache.clear_memory()
    _request_counts.clear()
    if previous_override is None:
        fastapi_app.dependency_overrides.pop(get_db, None)
    else:
        fastapi_app.dependency_overrides[get_db] = previous_override


@pytest.fixture(autouse=True)
def _recreate_tables():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/signup",
        json={"email": "usage.user@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_usage_summary_and_costs_track_analyze_requests(client):
    headers = _auth_headers(client)
    quota_response = client.post(
        "/quotas",
        headers=headers,
        json={"max_requests": 5, "alert_thresholds": [0.8, 1.0]},
    )
    assert quota_response.status_code == 200
    assert quota_response.json()["user_id"] is not None

    analyze_response = client.post(
        "/analyze/",
        headers=headers,
        json={"code": "print('hello')", "language": "python"},
    )
    assert analyze_response.status_code == 200

    summary_response = client.get("/usage/summary", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["scope"] == "user"
    assert summary["request_count"] == 1
    assert summary["total_tokens"] > 0
    assert summary["estimated_cost_usd"] == 0

    costs_response = client.get("/usage/costs", headers=headers)
    assert costs_response.status_code == 200
    costs = costs_response.json()
    assert costs["providers"][0]["provider"] == "rule-based"
    assert costs["providers"][0]["request_count"] == 1


def test_analyze_returns_429_when_user_quota_is_exceeded(client):
    headers = _auth_headers(client)
    quota_response = client.post(
        "/quotas",
        headers=headers,
        json={"period": "monthly", "max_requests": 1},
    )
    assert quota_response.status_code == 200

    first_response = client.post(
        "/analyze/",
        headers=headers,
        json={"code": "x = 1", "language": "python"},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/analyze/",
        headers=headers,
        json={"code": "x = 2", "language": "python"},
    )
    assert second_response.status_code == 429
    assert second_response.json()["detail"]["message"] == "Usage quota exceeded"
    assert "requests" in second_response.json()["detail"]["exceeded"]


def test_usage_summary_emits_alerts_at_configured_thresholds(client):
    headers = _auth_headers(client)
    quota_response = client.post(
        "/quotas",
        headers=headers,
        json={"max_requests": 1, "alert_thresholds": [0.8, 1.0]},
    )
    assert quota_response.status_code == 200

    analyze_response = client.post(
        "/analyze/",
        headers=headers,
        json={"code": "print('alert')", "language": "python"},
    )
    assert analyze_response.status_code == 200

    summary_response = client.get("/usage/summary", headers=headers)
    assert summary_response.status_code == 200
    alerts = summary_response.json()["alerts"]
    assert [alert["threshold"] for alert in alerts] == [0.8, 1.0]
    assert all(alert["metric"] == "requests" for alert in alerts)


def test_usage_and_quota_endpoints_require_authentication(client):
    for method, url in [
        ("get", "/usage/summary"),
        ("get", "/usage/costs"),
        ("get", "/quotas"),
        ("post", "/quotas"),
    ]:
        if method == "post":
            response = client.post(url, json={})
        else:
            response = client.get(url)
        assert response.status_code in (401, 422)


def test_quota_payload_validation_rejects_empty_limits_and_bad_thresholds(client):
    headers = _auth_headers(client)

    empty_limits = client.post("/quotas", headers=headers, json={})
    assert empty_limits.status_code == 422

    bad_threshold = client.post(
        "/quotas",
        headers=headers,
        json={"max_requests": 5, "alert_thresholds": [0, 1.2]},
    )
    assert bad_threshold.status_code == 422

    bad_period = client.get("/usage/summary?period=yearly", headers=headers)
    assert bad_period.status_code == 422


def test_user_cannot_manage_another_users_quota(client):
    first_headers = _auth_headers(client)
    second_signup = client.post(
        "/auth/signup",
        json={"email": "other.user@example.com", "password": "StrongPass123!"},
    )
    assert second_signup.status_code == 200

    response = client.post(
        "/quotas",
        headers=first_headers,
        json={"user_id": second_signup.json()["user_id"], "max_requests": 5},
    )
    assert response.status_code == 403


def test_quota_upsert_updates_existing_user_quota(client):
    headers = _auth_headers(client)
    first = client.post("/quotas", headers=headers, json={"max_requests": 3})
    second = client.post("/quotas", headers=headers, json={"max_requests": 7})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["max_requests"] == 7

    fetched = client.get("/quotas", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["max_requests"] == 7


def test_team_quota_takes_precedence_over_user_quota(client):
    headers = _auth_headers(client)
    user_quota = client.post("/quotas", headers=headers, json={"max_requests": 1})
    team_quota = client.post(
        "/quotas",
        headers=headers,
        json={"team_id": "core-platform", "max_requests": 2},
    )
    assert user_quota.status_code == 200
    assert team_quota.status_code == 200

    for code in ["x = 1", "x = 2"]:
        response = client.post(
            "/analyze/",
            headers={**headers, "X-Team-Id": "core-platform"},
            json={"code": code, "language": "python"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/analyze/",
        headers={**headers, "X-Team-Id": "core-platform"},
        json={"code": "x = 3", "language": "python"},
    )
    assert blocked.status_code == 429
    assert "requests" in blocked.json()["detail"]["exceeded"]


def test_token_quota_blocks_before_analysis_runs(client):
    headers = _auth_headers(client)
    quota_response = client.post("/quotas", headers=headers, json={"max_tokens": 1})
    assert quota_response.status_code == 200

    response = client.post(
        "/analyze/",
        headers=headers,
        json={"code": "print('more than one estimated token')", "language": "python"},
    )
    assert response.status_code == 429
    assert "tokens" in response.json()["detail"]["exceeded"]


def test_cached_analyze_requests_are_still_logged(client):
    headers = _auth_headers(client)
    payload = {"code": "print('cached')", "language": "python"}

    first = client.post("/analyze/", headers=headers, json=payload)
    second = client.post("/analyze/", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"

    summary = client.get("/usage/summary", headers=headers).json()
    assert summary["request_count"] == 2


def test_team_usage_summary_and_costs_are_isolated(client):
    headers = _auth_headers(client)

    team_response = client.post(
        "/analyze/",
        headers={**headers, "X-Team-Id": "team-a"},
        json={"code": "print('team')", "language": "python"},
    )
    user_response = client.post(
        "/analyze/",
        headers=headers,
        json={"code": "print('user')", "language": "python"},
    )
    assert team_response.status_code == 200
    assert user_response.status_code == 200

    team_summary = client.get(
        "/usage/summary?team_id=team-a",
        headers=headers,
    ).json()
    team_costs = client.get("/usage/costs?team_id=team-a", headers=headers).json()

    assert team_summary["scope"] == "team"
    assert team_summary["team_id"] == "team-a"
    assert team_summary["request_count"] == 1
    assert team_costs["providers"][0]["request_count"] == 1


def test_estimate_helpers_cover_empty_text_unknown_provider_and_thresholds():
    assert estimate_tokens("") == 1

    estimate = estimate_usage("abcd", provider="mystery-provider", model="custom")
    assert estimate.provider == "mystery-provider"
    assert estimate.model == "custom"
    assert estimate.total_tokens == 1
    assert estimate.estimated_cost_usd == 0.000002

    assert parse_thresholds("bad, 0, 0.8, 1.5, 1") == [0.8, 1.0]
    assert parse_thresholds("bad") == [0.8, 1.0]


def test_daily_aggregation_excludes_old_usage_rows():
    db = TEST_SESSION_LOCAL()
    try:
        now = datetime.now(UTC)
        db.add_all(
            [
                UsageLog(
                    user_id=1,
                    endpoint="/analyze/",
                    provider="rule-based",
                    model="qyverix-engine-v3",
                    prompt_tokens=10,
                    completion_tokens=0,
                    total_tokens=10,
                    estimated_cost_usd=0,
                    created_at=now - timedelta(days=2),
                ),
                UsageLog(
                    user_id=1,
                    endpoint="/analyze/",
                    provider="rule-based",
                    model="qyverix-engine-v3",
                    prompt_tokens=4,
                    completion_tokens=1,
                    total_tokens=5,
                    estimated_cost_usd=0,
                    created_at=now,
                ),
            ]
        )
        db.commit()

        daily = aggregate_usage(db, period="daily", user_id=1)
        monthly = aggregate_usage(db, period="monthly", user_id=1)
    finally:
        db.close()

    assert daily["request_count"] == 1
    assert daily["total_tokens"] == 5
    assert monthly["request_count"] == 2
    assert monthly["total_tokens"] == 15


def test_provider_costs_groups_by_provider_and_model():
    db = TEST_SESSION_LOCAL()
    try:
        db.add_all(
            [
                UsageLog(
                    user_id=2,
                    endpoint="/analyze/",
                    provider="openai",
                    model="gpt-4o-mini",
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                    estimated_cost_usd=0.00003,
                ),
                UsageLog(
                    user_id=2,
                    endpoint="/chat/message",
                    provider="openai",
                    model="gpt-4o-mini",
                    prompt_tokens=20,
                    completion_tokens=5,
                    total_tokens=25,
                    estimated_cost_usd=0.00005,
                ),
                UsageLog(
                    user_id=2,
                    endpoint="/chat/message",
                    provider="groq",
                    model="llama3",
                    prompt_tokens=10,
                    completion_tokens=0,
                    total_tokens=10,
                    estimated_cost_usd=0.000005,
                ),
            ]
        )
        db.commit()
        costs = provider_costs(db, user_id=2)
    finally:
        db.close()

    by_provider = {(item["provider"], item["model"]): item for item in costs}
    assert by_provider[("openai", "gpt-4o-mini")]["request_count"] == 2
    assert by_provider[("openai", "gpt-4o-mini")]["total_tokens"] == 40
    assert by_provider[("groq", "llama3")]["request_count"] == 1


def test_enforce_quota_blocks_cost_and_combined_limits():
    db = TEST_SESSION_LOCAL()
    try:
        db.add(
            QuotaConfig(
                user_id=9,
                period="monthly",
                max_requests=10,
                max_tokens=100,
                max_cost_usd=0.01,
            )
        )
        db.commit()

        estimate = UsageEstimate(
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            estimated_cost_usd=0.02,
        )
        with pytest.raises(Exception) as exc_info:
            enforce_quota(db, estimate, user_id=9)
    finally:
        db.close()

    assert getattr(exc_info.value, "status_code") == 429
    assert "cost" in exc_info.value.detail["exceeded"]


def test_build_alerts_returns_empty_without_quota_and_reports_multiple_metrics():
    assert build_alerts({"request_count": 1, "total_tokens": 1, "estimated_cost_usd": 0}, None) == []

    quota = QuotaConfig(
        max_requests=2,
        max_tokens=10,
        max_cost_usd=1,
        alert_thresholds="0.5,1",
    )
    alerts = build_alerts(
        {"request_count": 2, "total_tokens": 5, "estimated_cost_usd": 0.5},
        quota,
    )

    metrics = [alert["metric"] for alert in alerts]
    assert metrics.count("requests") == 2
    assert metrics.count("tokens") == 1
    assert metrics.count("cost") == 1
