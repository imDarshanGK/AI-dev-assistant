"""
Schema smoke tests.

Verify that Base.metadata.create_all() produces the expected tables and that
basic CRUD + FK operations succeed.  Run against PostgreSQL in CI (via the
DATABASE_URL env var) to catch dialect-specific issues that SQLite silently
ignores.  Falls back to SQLite when DATABASE_URL is not set so the suite can
also be executed locally without a running database server.

History-DB path is patched before any import-time side-effects occur so we
never pollute or depend on a real history.db file.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── path setup (mirrors conftest.py) ─────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Redirect history.db to a temp file before the module is first imported so
# that init_db() never touches the real filesystem path.
_tmp_history = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_history.close()

import app.services.database as _hist_db_module  # noqa: E402

_hist_db_module.DB_PATH = _tmp_history.name

from app import models as _models  # noqa: E402, F401  – registers all ORM models
from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402
    DigestSubscription,
    QueryHistory,
    SharedSnippet,
    User,
)

# ── expected tables ───────────────────────────────────────────────────────────
EXPECTED_TABLES = {
    "users",
    "query_history",
    "favorite_results",
    "digest_subscriptions",
    "shares",
}

# ── database URL (PostgreSQL in CI, SQLite locally) ───────────────────────────
_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test_schema_smoke.db")
_connect_args = (
    {"check_same_thread": False} if _DATABASE_URL.startswith("sqlite") else {}
)
_poolclass_kwargs = (
    {"poolclass": StaticPool} if _DATABASE_URL.startswith("sqlite:///:memory:") else {}
)


# ── fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(
        _DATABASE_URL, connect_args=_connect_args, **_poolclass_kwargs
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ── ORM schema tests ──────────────────────────────────────────────────────────
def test_all_orm_tables_exist(db_engine):
    """create_all() must produce every table declared in models.py."""
    existing = set(inspect(db_engine).get_table_names())
    missing = EXPECTED_TABLES - existing
    assert not missing, f"Tables not created by create_all(): {missing}"


def test_database_connection(db_engine):
    """Engine must reach the database and execute a trivial query."""
    with db_engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_user_insert_and_query(db_session):
    """Insert a User row and retrieve it by email."""
    from datetime import UTC, datetime

    user = User(
        email="smoke_user@test.local",
        password_hash="hashed_pw",
        created_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    fetched = db_session.query(User).filter_by(email="smoke_user@test.local").first()
    assert fetched is not None
    assert fetched.password_hash == "hashed_pw"


def test_unique_email_constraint(db_session):
    """users.email must have a UNIQUE constraint."""
    from datetime import UTC, datetime

    from sqlalchemy.exc import IntegrityError

    email = "dup_smoke@test.local"
    db_session.add(User(email=email, password_hash="a", created_at=datetime.now(UTC)))
    db_session.commit()

    db_session.add(User(email=email, password_hash="b", created_at=datetime.now(UTC)))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_query_history_foreign_key(db_session):
    """QueryHistory.user_id must reference a valid users.id."""
    from datetime import UTC, datetime

    user = User(
        email="fk_smoke@test.local", password_hash="x", created_at=datetime.now(UTC)
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    entry = QueryHistory(
        user_id=user.id,
        action="explain",
        code="print('hello')",
        result_json="{}",
        created_at=datetime.now(UTC),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    assert entry.id is not None
    assert entry.user_id == user.id


def test_cascade_delete(db_session):
    """Deleting a User must cascade-delete related QueryHistory rows."""
    from datetime import UTC, datetime

    user = User(
        email="cascade_smoke@test.local",
        password_hash="y",
        created_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    for i in range(2):
        db_session.add(
            QueryHistory(
                user_id=user.id,
                action="debug",
                code=f"code_{i}",
                result_json="{}",
                created_at=datetime.now(UTC),
            )
        )
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    remaining = db_session.query(QueryHistory).filter_by(user_id=user.id).count()
    assert remaining == 0, "Cascade delete did not remove child QueryHistory rows"


def test_shared_snippet_insert(db_session):
    """SharedSnippet must accept a write and retrieve by token."""
    snippet = SharedSnippet(
        token="smoke-token-abc123",
        code="x = 42",
        result_json='{"score": 99}',
    )
    db_session.add(snippet)
    db_session.commit()
    db_session.refresh(snippet)

    fetched = (
        db_session.query(SharedSnippet).filter_by(token="smoke-token-abc123").first()
    )
    assert fetched is not None
    assert fetched.code == "x = 42"


def test_digest_subscription_insert(db_session):
    """DigestSubscription must accept a write and retrieve by email."""
    sub = DigestSubscription(
        email="digest_smoke@test.local",
        unsubscribe_token="unsub-smoke-xyz",
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    fetched = (
        db_session.query(DigestSubscription)
        .filter_by(email="digest_smoke@test.local")
        .first()
    )
    assert fetched is not None
    assert fetched.is_active is True


# ── history DB (aiosqlite / FTS5) tests ───────────────────────────────────────
def test_history_db_init():
    """init_db() must create the history and fts_history tables without error."""
    asyncio.run(_hist_db_module.init_db())


def test_history_save_and_retrieve():
    """save_entry() and get_entries() must round-trip a record."""
    asyncio.run(_hist_db_module.init_db())
    row_id = asyncio.run(_hist_db_module.save_entry("print('smoke')", "python", 95, 1))
    assert isinstance(row_id, int) and row_id > 0

    entries = asyncio.run(_hist_db_module.get_entries(limit=10))
    assert any(e["language"] == "python" for e in entries)


def test_history_fts5_search():
    """FTS5 MATCH query must return rows containing the search term."""
    asyncio.run(_hist_db_module.init_db())
    asyncio.run(
        _hist_db_module.save_entry("def unique_smoke_fn(): pass", "python", 80, 0)
    )
    results = asyncio.run(_hist_db_module.search_entries("unique_smoke_fn"))
    assert any("unique_smoke_fn" in e["code_preview"] for e in results)


def test_history_delete():
    """delete_entry() must remove a record and return True."""
    asyncio.run(_hist_db_module.init_db())
    row_id = asyncio.run(
        _hist_db_module.save_entry("to_be_deleted = True", "python", 50, 3)
    )
    deleted = asyncio.run(_hist_db_module.delete_entry(row_id))
    assert deleted is True
