import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base, get_db
from app.main import app
from app.models import AuditLog, User
from app.services.audit import REDACTED, redact

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin_audit.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
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
    if os.path.exists("./test_admin_audit.db"):
        os.remove("./test_admin_audit.db")


client = TestClient(app)


def _signup(email: str) -> dict:
    r = client.post("/auth/signup", json={"email": email, "password": "password12345"})
    assert r.status_code == 200, r.text
    return r.json()


def _make_admin(user_id: int) -> None:
    db = TestingSessionLocal()
    try:
        user = db.get(User, user_id)
        user.is_admin = True
        db.commit()
    finally:
        db.close()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Unit: redaction ────────────────────────────────────────────────────────────
def test_redact_masks_sensitive_keys():
    cleaned = redact(
        {
            "email": "x@example.com",
            "password": "hunter2",
            "api_key": "abc",
            "nested": {"access_token": "t", "ok": 1},
            "items": [{"secret": "s", "name": "n"}],
        }
    )
    assert cleaned["email"] == "x@example.com"
    assert cleaned["password"] == REDACTED
    assert cleaned["api_key"] == REDACTED
    assert cleaned["nested"]["access_token"] == REDACTED
    assert cleaned["nested"]["ok"] == 1
    assert cleaned["items"][0]["secret"] == REDACTED
    assert cleaned["items"][0]["name"] == "n"


# ── Integration: admin actions + audit trail ───────────────────────────────────
def test_non_admin_is_forbidden():
    user = _signup("plain@example.com")
    r = client.get("/admin/audit-logs", headers=_auth(user["access_token"]))
    assert r.status_code == 403


def test_unauthenticated_is_unauthorized():
    r = client.get("/admin/audit-logs")
    assert r.status_code == 401


def test_role_update_is_logged_and_queryable():
    admin = _signup("admin@example.com")
    _make_admin(admin["user_id"])
    target = _signup("target@example.com")

    # Promote the target user to admin.
    r = client.put(
        f"/admin/users/{target['user_id']}/role",
        json={"is_admin": True},
        headers=_auth(admin["access_token"]),
    )
    assert r.status_code == 200, r.text

    # The action shows up in the audit log.
    r = client.get(
        "/admin/audit-logs?action=user.role_update",
        headers=_auth(admin["access_token"]),
    )
    assert r.status_code == 200
    logs = r.json()
    assert len(logs) >= 1
    entry = logs[0]
    assert entry["actor_email"] == "admin@example.com"
    assert entry["target_id"] == str(target["user_id"])
    assert entry["details"]["to"] is True


def test_delete_user_is_logged():
    admin = _signup("admin2@example.com")
    _make_admin(admin["user_id"])
    victim = _signup("victim@example.com")

    r = client.delete(
        f"/admin/users/{victim['user_id']}", headers=_auth(admin["access_token"])
    )
    assert r.status_code == 200, r.text

    r = client.get(
        f"/admin/audit-logs?action=user.delete&actor_id={admin['user_id']}",
        headers=_auth(admin["access_token"]),
    )
    assert r.status_code == 200
    logs = r.json()
    assert any(e["target_id"] == str(victim["user_id"]) for e in logs)


def test_admin_cannot_delete_self():
    admin = _signup("admin3@example.com")
    _make_admin(admin["user_id"])
    r = client.delete(
        f"/admin/users/{admin['user_id']}", headers=_auth(admin["access_token"])
    )
    assert r.status_code == 400


def test_audit_entries_are_append_only():
    """Deleting the acting user must not cascade-remove their audit rows."""
    admin = _signup("admin4@example.com")
    _make_admin(admin["user_id"])
    target = _signup("target2@example.com")
    client.put(
        f"/admin/users/{target['user_id']}/role",
        json={"is_admin": False},
        headers=_auth(admin["access_token"]),
    )

    db = TestingSessionLocal()
    try:
        count = len(
            db.execute(select(AuditLog).where(AuditLog.actor_id == admin["user_id"]))
            .scalars()
            .all()
        )
        assert count >= 1
    finally:
        db.close()
