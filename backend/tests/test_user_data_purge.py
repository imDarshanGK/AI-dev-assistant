"""Tests for authenticated user data purge flow."""

from datetime import timedelta

import pytest
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models import FavoriteResult, QueryHistory, User, UserDataPurgeAudit
from app.services.user_deletion import (
    CONFIRMATION_PHRASE,
    DATA_PURGE_RETENTION_DAYS,
    erase_expired_user_data,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
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
    Base.metadata.drop_all(bind=TEST_ENGINE)
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def _signup(
    client: TestClient,
    email: str,
    password: str = "StrongPass123!",
) -> tuple[int, dict[str, str]]:
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200

    data = response.json()
    return data["user_id"], {"Authorization": f"Bearer {data['access_token']}"}


def _create_history(client: TestClient, headers: dict[str, str], code: str) -> None:
    response = client.post(
        "/user/history",
        headers=headers,
        json={
            "action": "debugging",
            "code": code,
            "result_json": '{"issues": [], "clean": true}',
        },
    )
    assert response.status_code == 200


def _create_favorite(client: TestClient, headers: dict[str, str], title: str) -> None:
    response = client.post(
        "/user/favorites",
        headers=headers,
        json={
            "title": title,
            "action": "debugging",
            "code": "print('saved')",
            "result_json": '{"issues": [], "clean": true}',
        },
    )
    assert response.status_code == 200


def _db_count(
    model: (
        type[User]
        | type[QueryHistory]
        | type[FavoriteResult]
        | type[UserDataPurgeAudit]
    ),
) -> int:
    db = TEST_SESSION_LOCAL()
    try:
        return len(db.execute(select(model)).scalars().all())
    finally:
        db.close()


def test_preview_requires_authentication(client: TestClient):
    response = client.get("/user/data-purge/preview")

    assert response.status_code == 401


def test_purge_requires_authentication(client: TestClient):
    response = client.post(
        "/user/data-purge",
        json={"confirmation": CONFIRMATION_PHRASE},
    )

    assert response.status_code == 401


def test_preview_returns_current_user_data_counts(client: TestClient):
    user_id, headers = _signup(client, "preview@example.com")
    _create_history(client, headers, "print('one')")
    _create_history(client, headers, "print('two')")
    _create_favorite(client, headers, "Important result")

    response = client.get("/user/data-purge/preview", headers=headers)

    assert response.status_code == 200
    body = response.json()

    assert body["user_id"] == user_id
    assert body["history_records"] == 2
    assert body["favorite_records"] == 1
    assert body["account_will_be_deleted"] is True
    assert body["confirmation_phrase"] == CONFIRMATION_PHRASE
    assert body["deletion_status"] == "active"
    assert body["retention_days"] == DATA_PURGE_RETENTION_DAYS
    assert body["deletion_scheduled_for"] is None


def test_wrong_confirmation_deletes_nothing(client: TestClient):
    _, headers = _signup(client, "wrong-confirmation@example.com")
    _create_history(client, headers, "print('keep')")
    _create_favorite(client, headers, "Keep favorite")

    response = client.post(
        "/user/data-purge",
        headers=headers,
        json={"confirmation": "delete my data"},
    )

    assert response.status_code == 400
    assert _db_count(User) == 1
    assert _db_count(QueryHistory) == 1
    assert _db_count(FavoriteResult) == 1
    assert _db_count(UserDataPurgeAudit) == 0


def test_purge_schedules_current_user_data_without_immediate_hard_delete(
    client: TestClient,
):
    _, user_headers = _signup(client, "purge-me@example.com")
    _, other_headers = _signup(client, "keep-me@example.com")

    _create_history(client, user_headers, "print('delete history')")
    _create_favorite(client, user_headers, "Delete favorite")
    _create_history(client, other_headers, "print('keep history')")
    _create_favorite(client, other_headers, "Keep favorite")

    response = client.post(
        "/user/data-purge",
        headers=user_headers,
        json={"confirmation": CONFIRMATION_PHRASE},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "deletion_scheduled"
    assert body["history_deleted"] == 0
    assert body["favorites_deleted"] == 0
    assert body["account_deleted"] is False
    assert body["audit_recorded"] is True
    assert body["retention_days"] == DATA_PURGE_RETENTION_DAYS
    assert body["deletion_scheduled_for"] is not None

    assert _db_count(User) == 2
    assert _db_count(QueryHistory) == 2
    assert _db_count(FavoriteResult) == 2
    assert _db_count(UserDataPurgeAudit) == 1

    other_me_response = client.get("/auth/me", headers=other_headers)
    assert other_me_response.status_code == 200
    assert other_me_response.json()["email"] == "keep-me@example.com"

    db = TEST_SESSION_LOCAL()
    try:
        user = db.execute(
            select(User).where(User.email == "purge-me@example.com")
        ).scalar_one()
        assert user.deletion_status == "pending_deletion"
        assert user.deletion_requested_at is not None
        assert user.deletion_scheduled_for is not None
    finally:
        db.close()


def test_pending_deletion_user_token_is_rejected_after_purge_request(
    client: TestClient,
):
    _, headers = _signup(client, "token-invalidated@example.com")

    purge_response = client.post(
        "/user/data-purge",
        headers=headers,
        json={"confirmation": CONFIRMATION_PHRASE},
    )

    assert purge_response.status_code == 200
    assert purge_response.json()["status"] == "deletion_scheduled"

    me_response = client.get("/auth/me", headers=headers)

    assert me_response.status_code == 401
    assert me_response.json()["detail"] == "User is pending deletion"


def test_pending_deletion_user_cannot_login_again(client: TestClient):
    email = "pending-login@example.com"
    password = "StrongPass123!"
    _, headers = _signup(client, email, password)

    purge_response = client.post(
        "/user/data-purge",
        headers=headers,
        json={"confirmation": CONFIRMATION_PHRASE},
    )

    assert purge_response.status_code == 200

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )

    assert login_response.status_code == 401
    assert login_response.json()["detail"] == "Account is pending deletion"


def test_final_erase_deletes_user_data_after_retention_period(client: TestClient):
    _, user_headers = _signup(client, "erase-after-retention@example.com")
    _, other_headers = _signup(client, "keep-after-retention@example.com")

    _create_history(client, user_headers, "print('erase history')")
    _create_favorite(client, user_headers, "Erase favorite")
    _create_history(client, other_headers, "print('keep history')")
    _create_favorite(client, other_headers, "Keep favorite")

    response = client.post(
        "/user/data-purge",
        headers=user_headers,
        json={"confirmation": CONFIRMATION_PHRASE},
    )
    assert response.status_code == 200

    db = TEST_SESSION_LOCAL()
    try:
        user = db.execute(
            select(User).where(User.email == "erase-after-retention@example.com")
        ).scalar_one()

        before_retention = user.deletion_scheduled_for - timedelta(seconds=1)
        before_result = erase_expired_user_data(db, now=before_retention)

        assert before_result.users_erased == 0
        assert before_result.history_deleted == 0
        assert before_result.favorites_deleted == 0
        assert _db_count(User) == 2
        assert _db_count(QueryHistory) == 2
        assert _db_count(FavoriteResult) == 2

        after_retention = user.deletion_scheduled_for + timedelta(seconds=1)
        after_result = erase_expired_user_data(db, now=after_retention)

        assert after_result.users_erased == 1
        assert after_result.history_deleted == 1
        assert after_result.favorites_deleted == 1
        assert after_result.audits_updated == 1
        assert _db_count(User) == 1
        assert _db_count(QueryHistory) == 1
        assert _db_count(FavoriteResult) == 1

        audit = db.execute(select(UserDataPurgeAudit)).scalar_one()
        assert audit.status == "completed"
        assert audit.history_deleted == 1
        assert audit.favorites_deleted == 1
        assert audit.completed_at is not None
    finally:
        db.close()


def test_audit_record_does_not_store_sensitive_user_data(client: TestClient):
    email = "sensitive@example.com"
    _, headers = _signup(client, email)
    _create_history(client, headers, "print('secret code')")
    _create_favorite(client, headers, "Secret favorite")

    response = client.post(
        "/user/data-purge",
        headers=headers,
        json={"confirmation": CONFIRMATION_PHRASE},
    )

    assert response.status_code == 200

    db = TEST_SESSION_LOCAL()
    try:
        audit = db.execute(select(UserDataPurgeAudit)).scalar_one()
        audit_text = repr(audit.__dict__)

        assert audit.history_deleted == 0
        assert audit.favorites_deleted == 0
        assert audit.status == "scheduled"
        assert audit.completed_at is None

        assert email not in audit_text
        assert "secret code" not in audit_text
        assert "Secret favorite" not in audit_text
        assert ":" not in audit.email_hash

        user = db.execute(select(User).where(User.email == email)).scalar_one()
        erase_result = erase_expired_user_data(
            db,
            now=user.deletion_scheduled_for + timedelta(seconds=1),
        )

        assert erase_result.users_erased == 1

        updated_audit = db.execute(select(UserDataPurgeAudit)).scalar_one()
        updated_audit_text = repr(updated_audit.__dict__)

        assert updated_audit.history_deleted == 1
        assert updated_audit.favorites_deleted == 1
        assert updated_audit.status == "completed"
        assert updated_audit.completed_at is not None

        assert email not in updated_audit_text
        assert "secret code" not in updated_audit_text
        assert "Secret favorite" not in updated_audit_text
        assert ":" not in updated_audit.email_hash
    finally:
        db.close()


def test_user_with_no_saved_data_can_schedule_and_finally_erase_account(
    client: TestClient,
):
    _, headers = _signup(client, "empty@example.com")

    response = client.post(
        "/user/data-purge",
        headers=headers,
        json={"confirmation": CONFIRMATION_PHRASE},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "deletion_scheduled"
    assert body["history_deleted"] == 0
    assert body["favorites_deleted"] == 0
    assert body["account_deleted"] is False
    assert body["audit_recorded"] is True
    assert _db_count(User) == 1
    assert _db_count(UserDataPurgeAudit) == 1

    db = TEST_SESSION_LOCAL()
    try:
        user = db.execute(select(User)).scalar_one()
        result = erase_expired_user_data(
            db,
            now=user.deletion_scheduled_for + timedelta(seconds=1),
        )

        assert result.users_erased == 1
        assert result.history_deleted == 0
        assert result.favorites_deleted == 0
        assert result.audits_updated == 1
        assert _db_count(User) == 0

        audit = db.execute(select(UserDataPurgeAudit)).scalar_one()
        assert audit.status == "completed"
        assert audit.history_deleted == 0
        assert audit.favorites_deleted == 0
    finally:
        db.close()
