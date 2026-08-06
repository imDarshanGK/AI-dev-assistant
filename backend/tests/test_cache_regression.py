"""Regression tests for the cache service."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from app.services.cache import AppCache

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_cache(enabled: bool = True) -> AppCache:
    """Return a fresh in-memory AppCache instance with cache enabled/disabled."""
    with patch("app.services.cache.settings") as mock_settings:
        mock_settings.redis_url = None
        mock_settings.cache_enabled = enabled
        mock_settings.cache_ttl_seconds = 60
        mock_settings.cache_max_entries = 100
        return AppCache()


# ── Cache miss / hit ──────────────────────────────────────────────────────────


def test_cache_miss_returns_none():
    cache = make_cache()
    with patch("app.services.cache.settings.cache_enabled", True):
        result = cache.get("analyze:v1", "print('hello')")
    assert result is None


def test_cache_hit_returns_stored_value():
    cache = make_cache()
    payload = {"result": "ok", "language": "python"}

    with (
        patch("app.services.cache.settings.cache_enabled", True),
        patch("app.services.cache.settings.cache_ttl_seconds", 60),
        patch("app.services.cache.settings.cache_max_entries", 100),
    ):
        cache.set("analyze:v1", "print('hello')", payload)
        result = cache.get("analyze:v1", "print('hello')")

    assert result == payload


def test_cache_miss_for_different_code():
    cache = make_cache()
    payload = {"result": "ok"}

    with (
        patch("app.services.cache.settings.cache_enabled", True),
        patch("app.services.cache.settings.cache_ttl_seconds", 60),
        patch("app.services.cache.settings.cache_max_entries", 100),
    ):
        cache.set("analyze:v1", "code_a", payload)
        result = cache.get("analyze:v1", "code_b")

    assert result is None


def test_cache_set_overwrites_existing_value():
    cache = make_cache()
    first = {"result": "first"}
    second = {"result": "second"}

    with (
        patch("app.services.cache.settings.cache_enabled", True),
        patch("app.services.cache.settings.cache_ttl_seconds", 60),
        patch("app.services.cache.settings.cache_max_entries", 100),
    ):
        cache.set("analyze:v1", "same_code", first)
        cache.set("analyze:v1", "same_code", second)
        result = cache.get("analyze:v1", "same_code")

    assert result == second


# ── Cache disabled ────────────────────────────────────────────────────────────


def test_cache_get_returns_none_when_disabled():
    cache = make_cache(enabled=False)
    with patch("app.services.cache.settings.cache_enabled", False):
        result = cache.get("analyze:v1", "print('hello')")
    assert result is None


def test_cache_set_does_nothing_when_disabled():
    cache = make_cache(enabled=False)
    payload = {"result": "ok"}

    with patch("app.services.cache.settings.cache_enabled", False):
        cache.set("analyze:v1", "print('hello')", payload)

    with patch("app.services.cache.settings.cache_enabled", True):
        result = cache.get("analyze:v1", "print('hello')")

    assert result is None


# ── TTL expiry ────────────────────────────────────────────────────────────────


def test_cache_returns_none_after_ttl_expires():
    cache = make_cache()
    payload = {"result": "ok"}

    with (
        patch("app.services.cache.settings.cache_enabled", True),
        patch("app.services.cache.settings.cache_ttl_seconds", 1),
        patch("app.services.cache.settings.cache_max_entries", 100),
    ):
        cache.set("analyze:v1", "expiring_code", payload)

    # Manually expire the entry by backdating its expiry
    key = cache._make_key("analyze:v1", "expiring_code")
    with cache._memory_lock:
        _, stored_payload = cache._memory_store[key]
        cache._memory_store[key] = (time.time() - 1, stored_payload)

    with patch("app.services.cache.settings.cache_enabled", True):
        result = cache.get("analyze:v1", "expiring_code")

    assert result is None


# ── Max entries eviction ──────────────────────────────────────────────────────


def test_cache_evicts_oldest_entry_when_full():
    cache = make_cache()

    with (
        patch("app.services.cache.settings.cache_enabled", True),
        patch("app.services.cache.settings.cache_ttl_seconds", 60),
        patch("app.services.cache.settings.cache_max_entries", 3),
    ):
        cache.set("ns", "code_1", {"v": 1})
        cache.set("ns", "code_2", {"v": 2})
        cache.set("ns", "code_3", {"v": 3})
        # Adding a 4th entry should evict code_1
        cache.set("ns", "code_4", {"v": 4})

    with patch("app.services.cache.settings.cache_enabled", True):
        assert cache.get("ns", "code_1") is None
        assert cache.get("ns", "code_4") == {"v": 4}


# ── Namespace isolation ───────────────────────────────────────────────────────


def test_different_namespaces_dont_collide():
    cache = make_cache()
    payload_a = {"result": "namespace_a"}
    payload_b = {"result": "namespace_b"}

    with (
        patch("app.services.cache.settings.cache_enabled", True),
        patch("app.services.cache.settings.cache_ttl_seconds", 60),
        patch("app.services.cache.settings.cache_max_entries", 100),
    ):
        cache.set("namespace_a", "same_code", payload_a)
        cache.set("namespace_b", "same_code", payload_b)

        assert cache.get("namespace_a", "same_code") == payload_a
        assert cache.get("namespace_b", "same_code") == payload_b


# ── Clear memory ──────────────────────────────────────────────────────────────


def test_clear_memory_removes_all_entries():
    cache = make_cache()
    payload = {"result": "ok"}

    with (
        patch("app.services.cache.settings.cache_enabled", True),
        patch("app.services.cache.settings.cache_ttl_seconds", 60),
        patch("app.services.cache.settings.cache_max_entries", 100),
    ):
        cache.set("analyze:v1", "code_a", payload)
        cache.set("analyze:v1", "code_b", payload)

    cache.clear_memory()

    with patch("app.services.cache.settings.cache_enabled", True):
        assert cache.get("analyze:v1", "code_a") is None
        assert cache.get("analyze:v1", "code_b") is None


# ── Redis failure graceful degradation ───────────────────────────────────────


def test_redis_get_failure_falls_back_to_memory():
    import sys
    import types

    fake_redis_module = types.ModuleType("redis")
    mock_redis_instance = MagicMock()
    mock_redis_instance.get.side_effect = Exception("Redis connection failed")
    fake_redis_class = MagicMock(return_value=mock_redis_instance)
    fake_redis_class.from_url = MagicMock(return_value=mock_redis_instance)
    fake_redis_module.Redis = fake_redis_class

    with patch.dict(sys.modules, {"redis": fake_redis_module}):
        with patch("app.services.cache.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"
            mock_settings.cache_enabled = True
            mock_settings.cache_ttl_seconds = 60
            mock_settings.cache_max_entries = 100
            cache = AppCache()

        with patch("app.services.cache.settings.cache_enabled", True):
            result = cache.get("analyze:v1", "some_code")

    assert result is None


def test_redis_set_failure_does_not_raise():
    import sys
    import types

    fake_redis_module = types.ModuleType("redis")
    mock_redis_instance = MagicMock()
    mock_redis_instance.setex.side_effect = Exception("Redis connection failed")
    fake_redis_class = MagicMock(return_value=mock_redis_instance)
    fake_redis_class.from_url = MagicMock(return_value=mock_redis_instance)
    fake_redis_module.Redis = fake_redis_class

    with patch.dict(sys.modules, {"redis": fake_redis_module}):
        with patch("app.services.cache.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"
            mock_settings.cache_enabled = True
            mock_settings.cache_ttl_seconds = 60
            mock_settings.cache_max_entries = 100
            cache = AppCache()

        with patch("app.services.cache.settings.cache_enabled", True):
            with patch("app.services.cache.settings.cache_ttl_seconds", 60):
                with patch("app.services.cache.settings.cache_max_entries", 100):
                    cache.set("analyze:v1", "some_code", {"result": "ok"})
