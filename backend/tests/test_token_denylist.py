import time

import pytest
import redis as redis_lib
from app.config import settings
from app.token_denylist import (
    InMemoryTokenDenylist,
    RedisTokenDenylist,
    _build_token_denylist,
)

# A separate DB index from whatever local dev might use, so these tests never
# collide with data a developer is inspecting by hand.
_TEST_REDIS_URL = "redis://localhost:6379/15"


def _redis_available() -> bool:
    try:
        redis_lib.Redis.from_url(_TEST_REDIS_URL, socket_connect_timeout=1).ping()
        return True
    except Exception:
        return False


requires_redis = pytest.mark.skipif(
    not _redis_available(), reason="no local Redis reachable on db 15"
)


def test_in_memory_revoke_then_is_revoked():
    denylist = InMemoryTokenDenylist()

    denylist.revoke("jti-1", expires_at=time.time() + 60)

    assert denylist.is_revoked("jti-1") is True


def test_in_memory_unrevoked_jti_is_not_revoked():
    denylist = InMemoryTokenDenylist()

    assert denylist.is_revoked("never-seen") is False


def test_in_memory_expired_entry_is_treated_as_not_revoked():
    denylist = InMemoryTokenDenylist()
    denylist.revoke("jti-expired", expires_at=time.time() - 1)

    assert denylist.is_revoked("jti-expired") is False
    # The stale bookkeeping entry should also have been purged.
    assert "jti-expired" not in denylist._revoked


def test_in_memory_falsy_jti_is_ignored():
    denylist = InMemoryTokenDenylist()

    denylist.revoke("", expires_at=time.time() + 60)

    assert denylist.is_revoked("") is False
    assert denylist._revoked == {}


def test_in_memory_clear_forgets_all_revocations():
    denylist = InMemoryTokenDenylist()
    denylist.revoke("jti-1", expires_at=time.time() + 60)

    denylist.clear()

    assert denylist.is_revoked("jti-1") is False


@requires_redis
def test_redis_revoke_then_is_revoked():
    denylist = RedisTokenDenylist(_TEST_REDIS_URL)
    denylist.clear()

    denylist.revoke("jti-1", expires_at=time.time() + 60)

    assert denylist.is_revoked("jti-1") is True
    denylist.clear()


@requires_redis
def test_redis_unrevoked_jti_is_not_revoked():
    denylist = RedisTokenDenylist(_TEST_REDIS_URL)
    denylist.clear()

    assert denylist.is_revoked("never-seen") is False


@requires_redis
def test_redis_key_ttl_matches_remaining_token_lifetime():
    denylist = RedisTokenDenylist(_TEST_REDIS_URL)
    denylist.clear()

    denylist.revoke("jti-1", expires_at=time.time() + 30)

    ttl = denylist._client.ttl(denylist._KEY_PREFIX + "jti-1")
    assert 0 < ttl <= 30
    denylist.clear()


@requires_redis
def test_redis_falsy_jti_is_ignored():
    denylist = RedisTokenDenylist(_TEST_REDIS_URL)
    denylist.clear()

    denylist.revoke("", expires_at=time.time() + 60)

    assert denylist.is_revoked("") is False


@requires_redis
def test_redis_clear_forgets_all_revocations():
    denylist = RedisTokenDenylist(_TEST_REDIS_URL)
    denylist.revoke("jti-1", expires_at=time.time() + 60)

    denylist.clear()

    assert denylist.is_revoked("jti-1") is False


@requires_redis
def test_redis_denylist_is_shared_across_instances():
    """Two separate clients pointed at the same Redis see each other's revocations,
    which is the multi-replica scenario this store exists to fix."""
    pod_a = RedisTokenDenylist(_TEST_REDIS_URL)
    pod_a.clear()
    pod_b = RedisTokenDenylist(_TEST_REDIS_URL)

    pod_a.revoke("jti-1", expires_at=time.time() + 60)

    assert pod_b.is_revoked("jti-1") is True
    pod_a.clear()


def test_build_token_denylist_uses_in_memory_when_redis_url_unset(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", None)

    denylist = _build_token_denylist()

    assert isinstance(denylist, InMemoryTokenDenylist)


@requires_redis
def test_build_token_denylist_uses_redis_when_reachable(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", _TEST_REDIS_URL)

    denylist = _build_token_denylist()

    assert isinstance(denylist, RedisTokenDenylist)


def test_build_token_denylist_falls_back_when_redis_unreachable(monkeypatch, caplog):
    # Port 1 on localhost is not listening, so the connection is refused
    # immediately rather than hanging for the configured connect timeout.
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")

    with caplog.at_level("WARNING"):
        denylist = _build_token_denylist()

    assert isinstance(denylist, InMemoryTokenDenylist)
    assert "falling back to an in-memory token denylist" in caplog.text
