"""Tests for improved error handling in the cache service."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from app.services.cache import AppCache


def make_cache(enabled: bool = True) -> AppCache:
    with patch("app.services.cache.settings") as mock_settings:
        mock_settings.redis_url = None
        mock_settings.cache_enabled = enabled
        mock_settings.cache_ttl_seconds = 60
        mock_settings.cache_max_entries = 100
        return AppCache()


# ── Non-dict payload rejection ────────────────────────────────────────────────


def test_set_rejects_list_payload():
    cache = make_cache()
    with patch("app.services.cache.settings.cache_enabled", True):
        with patch("app.services.cache.settings.cache_ttl_seconds", 60):
            with patch("app.services.cache.settings.cache_max_entries", 100):
                cache.set("ns", "code", ["not", "a", "dict"])

    with patch("app.services.cache.settings.cache_enabled", True):
        result = cache.get("ns", "code")
    assert result is None


def test_set_rejects_string_payload():
    cache = make_cache()
    with patch("app.services.cache.settings.cache_enabled", True):
        with patch("app.services.cache.settings.cache_ttl_seconds", 60):
            with patch("app.services.cache.settings.cache_max_entries", 100):
                cache.set("ns", "code", "not a dict")

    with patch("app.services.cache.settings.cache_enabled", True):
        result = cache.get("ns", "code")
    assert result is None


def test_set_rejects_none_payload():
    cache = make_cache()
    with patch("app.services.cache.settings.cache_enabled", True):
        with patch("app.services.cache.settings.cache_ttl_seconds", 60):
            with patch("app.services.cache.settings.cache_max_entries", 100):
                cache.set("ns", "code", None)

    with patch("app.services.cache.settings.cache_enabled", True):
        result = cache.get("ns", "code")
    assert result is None


# ── Invalid TTL rejection ─────────────────────────────────────────────────────


def test_set_skips_cache_when_ttl_is_zero():
    cache = make_cache()
    with patch("app.services.cache.settings.cache_enabled", True):
        with patch("app.services.cache.settings.cache_ttl_seconds", 0):
            with patch("app.services.cache.settings.cache_max_entries", 100):
                cache.set("ns", "code", {"result": "ok"})

    with patch("app.services.cache.settings.cache_enabled", True):
        result = cache.get("ns", "code")
    assert result is None


def test_set_skips_cache_when_ttl_is_negative():
    cache = make_cache()
    with patch("app.services.cache.settings.cache_enabled", True):
        with patch("app.services.cache.settings.cache_ttl_seconds", -10):
            with patch("app.services.cache.settings.cache_max_entries", 100):
                cache.set("ns", "code", {"result": "ok"})

    with patch("app.services.cache.settings.cache_enabled", True):
        result = cache.get("ns", "code")
    assert result is None


# ── Corrupted Redis JSON ───────────────────────────────────────────────────────


def test_redis_get_returns_none_on_corrupted_json():
    fake_redis_module = types.ModuleType("redis")
    mock_redis_instance = MagicMock()
    mock_redis_instance.get.return_value = b"not-valid-json{{{"
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
            result = cache.get("ns", "code")

    assert result is None


def test_redis_get_returns_none_on_non_dict_json():
    fake_redis_module = types.ModuleType("redis")
    mock_redis_instance = MagicMock()
    mock_redis_instance.get.return_value = b'["a", "list", "not", "a", "dict"]'
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
            result = cache.get("ns", "code")

    assert result is None


# ── Valid dict payload still works ────────────────────────────────────────────


def test_set_accepts_valid_dict_payload():
    cache = make_cache()
    payload = {"result": "ok", "language": "python"}

    with patch("app.services.cache.settings.cache_enabled", True):
        with patch("app.services.cache.settings.cache_ttl_seconds", 60):
            with patch("app.services.cache.settings.cache_max_entries", 100):
                cache.set("ns", "code", payload)
                result = cache.get("ns", "code")

    assert result == payload
