"""Integration tests for the compliance reporting pipeline."""

import json
import os
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import QueryHistory

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


# ── Helpers ────────────────────────────────────────────────────────────────────


def _signup(client, email="audit.user@example.com"):
    response = client.post(
        "/auth/signup", json={"email": email, "password": "StrongPass123!"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["user_id"], {"Authorization": f"Bearer {data['access_token']}"}


def _make_result(language="python", score=80, severities=None):
    severities = severities or []
    issues = [
        {
            "type": "bug",
            "line": 1,
            "description": "issue",
            "suggestion": "fix it",
            "severity": sev,
        }
        for sev in severities
    ]
    return json.dumps(
        {
            "explanation": {"language": language},
            "suggestions": {"overall_score": score},
            "debugging": {"issues": issues},
        }
    )


def _seed(user_id, *, action="analyze", language="python", score=80,
          severities=None, code="print(1)", created_at=None):
    db = TEST_SESSION_LOCAL()
    try:
        entry = QueryHistory(
            user_id=user_id,
            action=action,
            code=code,
            result_json=_make_result(language, score, severities),
        )
        if created_at is not None:
            entry.created_at = created_at
        db.add(entry)
        db.commit()
    finally:
        db.close()


# ── Authorization ──────────────────────────────────────────────────────────────


def test_report_endpoints_require_auth(client):
    assert client.post("/reports/generate", json={"format": "json"}).status_code == 401
    assert client.post("/reports/preview", json={}).status_code == 401
    assert client.get("/reports/audit").status_code == 401


# ── Metadata & generation ──────────────────────────────────────────────────────


def test_json_report_has_compliance_metadata_and_records(client):
    user_id, headers = _signup(client)
    _seed(user_id, language="python", score=90, severities=["error", "warning"])
    _seed(user_id, language="javascript", score=70, severities=["info"])

    response = client.post("/reports/generate", json={"format": "json"}, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]

    report = response.json()
    meta = report["metadata"]
    assert meta["report_id"]
    assert meta["generated_by"]["email"] == "audit.user@example.com"
    assert meta["analysis_version"] == "3.0.0"
    assert meta["record_count"] == 2
    assert "filters" in meta

    summary = report["summary"]
    assert summary["total_records"] == 2
    assert summary["total_issues"] == 3
    assert summary["by_severity"] == {"error": 1, "warning": 1, "info": 1}
    assert summary["average_score"] == 80.0
    assert len(report["records"]) == 2


def test_csv_export_contains_metadata_and_table(client):
    user_id, headers = _signup(client)
    _seed(user_id, language="python", score=88, severities=["error"])

    response = client.post("/reports/generate", json={"format": "csv"}, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    body = response.text
    assert "# Compliance Report" in body
    assert "report_id" in body
    assert "# Records" in body
    assert "code_preview" in body
    assert "python" in body


def test_pdf_export_is_valid_pdf(client):
    user_id, headers = _signup(client)
    _seed(user_id, language="python", score=75, severities=["warning", "info"])

    response = client.post("/reports/generate", json={"format": "pdf"}, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-report-id"]

    content = response.content
    assert content.startswith(b"%PDF-")
    assert b"%%EOF" in content
    assert len(content) > 500


# ── Filtering ──────────────────────────────────────────────────────────────────


def test_language_filter(client):
    user_id, headers = _signup(client)
    _seed(user_id, language="python")
    _seed(user_id, language="javascript")

    response = client.post(
        "/reports/preview",
        json={"filters": {"languages": ["python"]}},
        headers=headers,
    )
    assert response.status_code == 200
    report = response.json()
    assert report["summary"]["total_records"] == 1
    assert report["records"][0]["language"] == "python"


def test_severity_filter(client):
    user_id, headers = _signup(client)
    _seed(user_id, severities=["error"])
    _seed(user_id, severities=["info"])

    response = client.post(
        "/reports/preview",
        json={"filters": {"severities": ["error"]}},
        headers=headers,
    )
    report = response.json()
    assert report["summary"]["total_records"] == 1
    assert report["records"][0]["severity_counts"]["error"] == 1


def test_score_range_filter(client):
    user_id, headers = _signup(client)
    _seed(user_id, score=95)
    _seed(user_id, score=40)

    response = client.post(
        "/reports/preview",
        json={"filters": {"min_score": 80}},
        headers=headers,
    )
    report = response.json()
    assert report["summary"]["total_records"] == 1
    assert report["records"][0]["score"] == 95


def test_date_range_filter(client):
    user_id, headers = _signup(client)
    _seed(user_id, code="old", created_at=datetime(2023, 1, 1, 12, 0, 0))
    _seed(user_id, code="new", created_at=datetime(2025, 6, 1, 12, 0, 0))

    response = client.post(
        "/reports/preview",
        json={"filters": {"start_date": "2024-01-01T00:00:00"}},
        headers=headers,
    )
    report = response.json()
    assert report["summary"]["total_records"] == 1
    assert report["records"][0]["code_preview"] == "new"


def test_invalid_date_range_is_rejected(client):
    _, headers = _signup(client)
    response = client.post(
        "/reports/preview",
        json={
            "filters": {
                "start_date": "2025-06-01T00:00:00",
                "end_date": "2025-01-01T00:00:00",
            }
        },
        headers=headers,
    )
    assert response.status_code == 422


# ── Audit trail ────────────────────────────────────────────────────────────────


def test_generation_records_audit_event(client):
    user_id, headers = _signup(client)
    _seed(user_id)

    gen = client.post("/reports/generate", json={"format": "csv"}, headers=headers)
    report_id = gen.headers["x-report-id"]

    audit = client.get("/reports/audit", headers=headers)
    assert audit.status_code == 200
    events = audit.json()
    assert any(
        e["action"] == "report.generate"
        and e["resource"] == report_id
        and e["detail"].get("format") == "csv"
        for e in events
    )


def test_reports_are_scoped_to_the_requesting_user(client):
    user_a, headers_a = _signup(client, email="a@example.com")
    user_b, headers_b = _signup(client, email="b@example.com")
    _seed(user_a, code="a-secret")
    _seed(user_b, code="b-secret")

    report = client.post(
        "/reports/preview", json={}, headers=headers_a
    ).json()
    previews = [r["code_preview"] for r in report["records"]]
    assert previews == ["a-secret"]

    # User B generates a report; User A's audit trail must not expose it.
    client.post("/reports/generate", json={"format": "json"}, headers=headers_b)
    audit_a = client.get("/reports/audit", headers=headers_a).json()
    assert [e["action"] for e in audit_a] == ["report.preview"]
