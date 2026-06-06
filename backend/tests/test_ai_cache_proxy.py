"""
tests/test_ai_cache_proxy.py
----------------------------
Unit tests for the dev-time AI provider cache proxy.

Run with:
    DEV_CACHE_ENABLED=true pytest tests/test_ai_cache_proxy.py -v
"""

import json
import os
import time
# Activate the cache before importing the module under test.
os.environ["DEV_CACHE_ENABLED"] = "true"
os.environ["DEV_CACHE_DIR"] = ".test_ai_cache"
os.environ["DEV_CACHE_TTL_SECONDS"] = "5"  # short TTL for expiry tests
import pytest
from app.services import ai_cache_proxy as proxy  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


SAMPLE_REQUEST = {"model": "gpt-4o-mini", "code": "print('hello')", "language": "python"}
SAMPLE_RESPONSE = {"choices": [{"message": {"content": "Looks good!"}}]}


@pytest.fixture(autouse=True)
def clean_cache():
    """Start each test with an empty cache directory."""
    proxy.clear_all()
    yield
    proxy.clear_all()


# ---------------------------------------------------------------------------
# Cache miss
# ---------------------------------------------------------------------------


def test_get_cached_returns_none_on_miss():
    result = proxy.get_cached(SAMPLE_REQUEST)
    assert result is None


# ---------------------------------------------------------------------------
# Cache write → read round-trip
# ---------------------------------------------------------------------------


def test_set_and_get_cached_round_trip():
    proxy.set_cached(SAMPLE_REQUEST, SAMPLE_RESPONSE)
    result = proxy.get_cached(SAMPLE_REQUEST)
    assert result == SAMPLE_RESPONSE


def test_different_payloads_have_different_keys():
    other_request = {**SAMPLE_REQUEST, "code": "x = 1 / 0"}
    proxy.set_cached(SAMPLE_REQUEST, SAMPLE_RESPONSE)
    # Different request → should be a cache miss.
    assert proxy.get_cached(other_request) is None


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------


def test_expired_entry_returns_none(monkeypatch):
    proxy.set_cached(SAMPLE_REQUEST, SAMPLE_RESPONSE)

    # Fast-forward time past the TTL.
    future = time.time() + proxy._TTL + 1
    monkeypatch.setattr(time, "time", lambda: future)

    result = proxy.get_cached(SAMPLE_REQUEST)
    assert result is None


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------


def test_invalidate_removes_entry():
    proxy.set_cached(SAMPLE_REQUEST, SAMPLE_RESPONSE)
    removed = proxy.invalidate(SAMPLE_REQUEST)
    assert removed is True
    assert proxy.get_cached(SAMPLE_REQUEST) is None


def test_invalidate_nonexistent_entry_returns_false():
    assert proxy.invalidate({"model": "does-not-exist"}) is False


# ---------------------------------------------------------------------------
# Clear all
# ---------------------------------------------------------------------------


def test_clear_all_removes_every_entry():
    proxy.set_cached(SAMPLE_REQUEST, SAMPLE_RESPONSE)
    proxy.set_cached({"model": "other"}, {"foo": "bar"})
    removed = proxy.clear_all()
    assert removed == 2
    assert proxy.get_cached(SAMPLE_REQUEST) is None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def test_cache_stats_reflects_written_entries():
    proxy.set_cached(SAMPLE_REQUEST, SAMPLE_RESPONSE)
    stats = proxy.cache_stats()
    assert stats["enabled"] is True
    assert stats["total_files"] == 1
    assert stats["valid_entries"] == 1
    assert stats["expired_entries"] == 0


def test_cache_stats_empty_directory():
    stats = proxy.cache_stats()
    assert stats.get("total_files", 0) == 0


# ---------------------------------------------------------------------------
# Sensitive data warning (smoke test — just ensure it doesn't crash)
# ---------------------------------------------------------------------------


def test_sensitive_payload_logs_warning(caplog):
    sensitive = {**SAMPLE_REQUEST, "api_key": "sk-secret-12345"}
    import logging

    with caplog.at_level(logging.WARNING, logger="ai_cache_proxy"):
        proxy.set_cached(sensitive, SAMPLE_RESPONSE)

    assert any("sensitive" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# Disabled cache
# ---------------------------------------------------------------------------


def test_cache_disabled_always_returns_none(monkeypatch):
    monkeypatch.setattr(proxy, "_ENABLED", False)
    proxy.set_cached(SAMPLE_REQUEST, SAMPLE_RESPONSE)  # should be a no-op
    assert proxy.get_cached(SAMPLE_REQUEST) is None


# ---------------------------------------------------------------------------
# Key determinism
# ---------------------------------------------------------------------------


def test_cache_key_is_deterministic():
    key1 = proxy._make_cache_key({"b": 2, "a": 1})
    key2 = proxy._make_cache_key({"a": 1, "b": 2})
    assert key1 == key2  # sort_keys=True ensures this