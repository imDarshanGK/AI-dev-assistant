from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app import database
from app.database import Base
from app.main import app
from app.models import AuditLog, SharedSnippet, User
from app.security import get_current_user
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


def test_delete_share_authorization(monkeypatch, tmp_path):
    session_local = _configure_test_db(monkeypatch, tmp_path)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    db = session_local()

    # 1. Create our pretend users in the database
    owner = User(email="owner@test.com", password_hash="fake_pass", is_admin=False)
    admin = User(email="admin@test.com", password_hash="fake_pass", is_admin=True)
    stranger = User(
        email="stranger@test.com", password_hash="fake_pass", is_admin=False
    )
    db.add_all([owner, admin, stranger])
    db.commit()

    # 2. Create pretend shares owned by the 'owner'
    share1 = SharedSnippet(
        token="token1", code="print('1')", result_json="{}", user_id=owner.id
    )
    share2 = SharedSnippet(
        token="token2", code="print('2')", result_json="{}", user_id=owner.id
    )
    db.add_all([share1, share2])
    db.commit()

    # 3. Test Scenario A: Stranger tries to delete (Should Fail - 403)
    app.dependency_overrides[get_current_user] = lambda: stranger
    resp_stranger = client.delete("/share/token1")
    assert resp_stranger.status_code == 403

    # 4. Test Scenario B: Owner tries to delete (Should Succeed - 204)
    app.dependency_overrides[get_current_user] = lambda: owner
    resp_owner = client.delete("/share/token1")
    assert resp_owner.status_code == 204

    # 5. Test Scenario C: Admin tries to delete (Should Succeed - 204)
    app.dependency_overrides[get_current_user] = lambda: admin
    resp_admin = client.delete("/share/token2")
    assert resp_admin.status_code == 204

    # Cleanup our overrides and close database
    app.dependency_overrides.clear()
    db.close()
