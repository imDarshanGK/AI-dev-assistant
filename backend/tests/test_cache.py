import hashlib
import time

import pytest
from app.config import settings
from app.services.cache import AppCache


def test_cache_key_uses_sha256_digest(monkeypatch):
    """Verify _make_key produces a SHA-256 based key with the v2 prefix."""
    monkeypatch.setattr(settings, "cache_enabled", True)
    code = "python\nprint('hello')"

    key = AppCache()._make_key("analyze:v1", code)

    expected_digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    assert key == f"ai-assistant:v2:analyze:v1:{expected_digest}"


def test_cache_key_does_not_use_md5(monkeypatch):
    """Ensure the generated key does NOT match an MD5-based key."""
    monkeypatch.setattr(settings, "cache_enabled", True)
    code = "python\nprint('hello')"

    key = AppCache()._make_key("analyze:v1", code)

    md5_digest = hashlib.md5(code.encode("utf-8")).hexdigest()
    assert md5_digest not in key


@pytest.fixture
def memory_cache():
    original_url = settings.redis_url
    settings.redis_url = None
    cache = AppCache()
    settings.redis_url = original_url
    return cache


def test_cache_set_and_get_success(memory_cache, monkeypatch):
    monkeypatch.setattr(settings, "cache_enabled", True)
    monkeypatch.setattr(settings, "cache_ttl_seconds", 60)

    memory_cache.set("test_namespace", "my_code", {"data": "success"})
    result = memory_cache.get("test_namespace", "my_code")

    assert result is not None
    assert result["data"] == "success"


def test_cache_disabled_returns_none(memory_cache, monkeypatch):
    monkeypatch.setattr(settings, "cache_enabled", False)

    memory_cache.set("disabled_ns", "code123", {"data": "hidden"})
    result = memory_cache.get("disabled_ns", "code123")

    assert result is None


def test_cache_expiration(memory_cache, monkeypatch):
    monkeypatch.setattr(settings, "cache_enabled", True)
    monkeypatch.setattr(settings, "cache_ttl_seconds", -1)

    memory_cache.set("expire_ns", "code123", {"data": "gone"})
    result = memory_cache.get("expire_ns", "code123")

    assert result is None
