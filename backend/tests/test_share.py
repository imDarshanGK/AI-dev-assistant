from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app import database
from app.database import Base
from app.main import app
from app.models import SharedSnippet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


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


def test_delete_share_unauthorized(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # 1. Create a dummy share to try and delete
    payload = {
        "code": "print('hello')",
        "result": {"provider": "rule-based", "explanation": {"summary": "ok"}},
    }
    create_resp = client.post("/share/", json=payload)
    share_id = create_resp.json()["id"]

    # 2. Attempt to delete WITHOUT being logged in (no bouncer pass!)
    delete_resp = client.delete(f"/share/{share_id}")

    # 3. Prove that the bouncer kicked them out (401 Unauthorized or 403 Forbidden)
    assert delete_resp.status_code in [401, 403]


def test_delete_share_authorized(monkeypatch, tmp_path):
    _configure_test_db(monkeypatch, tmp_path)
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # 1. Create a dummy share
    payload = {
        "code": "print('hello')",
        "result": {"provider": "rule-based", "explanation": {"summary": "ok"}},
    }
    create_resp = client.post("/share/", json=payload)
    share_id = create_resp.json()["id"]

    # 2. Bribe the bouncer! (Mock a logged-in user)
    from app.models import User
    from app.security import get_current_user

    def mock_user():
        return User(id=999, email="leader@neural-knights.com")

    app.dependency_overrides[get_current_user] = mock_user

    # 3. Delete the share as an authorized user!
    delete_resp = client.delete(f"/share/{share_id}")

    # 4. Prove it was successfully deleted (204 No Content)
    assert delete_resp.status_code == 204

    # 5. Try to fetch it again to prove the castle is truly gone!
    fetch_resp = client.get(f"/share/{share_id}")
    assert fetch_resp.status_code == 404

    # 6. Clean up our bribe so we don't mess up other tests
    app.dependency_overrides.clear()
