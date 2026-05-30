from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.database import Base
from app.main import app
from app.models import SharedSnippet


def _configure_test_db(monkeypatch, tmp_path):
    db_path = tmp_path / "share-tests.db"

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    return session_local


def test_create_and_fetch_share(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    payload = {
        "code": "print('hello')",
        "result": {
            "provider": "rule-based",
            "explanation": {"summary": "ok"},
        },
    }

    create_resp = client.post("/share/", json=payload)

    assert create_resp.status_code == 200

    share_id = create_resp.json()["id"]

    assert share_id

    fetch_resp = client.get(f"/share/{share_id}")

    assert fetch_resp.status_code == 200

    data = fetch_resp.json()

    assert data["id"] == share_id
    assert data["code"] == payload["code"]
    assert data["result"] == payload["result"]
    assert "created_at" in data


def test_expired_share_returns_404(monkeypatch, tmp_path):
    session_local = _configure_test_db(monkeypatch, tmp_path)

    from fastapi.testclient import TestClient

    client = TestClient(app)

    db = session_local()

    record = SharedSnippet(
        token="expired123",
        code="print('old')",
        result_json='{"ok": true}',
        created_at=datetime.now(UTC) - timedelta(days=8),
    )

    db.add(record)
    db.commit()
    db.close()

    resp = client.get("/share/expired123")

    assert resp.status_code == 404
    assert "expired" in resp.json()["detail"].lower()