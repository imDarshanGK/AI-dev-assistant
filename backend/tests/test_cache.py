"""
Cache tests for analysis result caching.
"""

import time

from app.services.cache import cache


def test_cache_miss():
    """
    Requesting a non-existent cache entry should return None.
    """
    result = cache.get("test", "non-existent-code")
    assert result is None


def test_cache_hit():
    """
    Cached entries should be returned successfully.
    """
    payload = {"status": "cached"}

    cache.set("test", "sample-code", payload)

    result = cache.get("test", "sample-code")

    assert result == payload


def test_cache_expiration():
    """
    Expired cache entries should be invalidated automatically.
    """
    key = cache._make_key("test", "expired-code")

    with cache._memory_lock:
        cache._memory_store[key] = (
            time.time() - 10,
            {"expired": True},
        )

    result = cache.get("test", "expired-code")

    assert result is None


def test_cleanup_expired():
    """
    Cleanup routine should remove expired entries.
    """
    key = cache._make_key("test", "cleanup-code")

    with cache._memory_lock:
        cache._memory_store[key] = (
            time.time() - 10,
            {"expired": True},
        )

    removed = cache.cleanup_expired()

    assert removed >= 1
import hashlib

from app.services.cache import AppCache


def test_cache_key_uses_sha256_digest():
    """Verify _make_key produces a SHA-256 based key with the v2 prefix."""
    code = "python\nprint('hello')"

    key = AppCache()._make_key("analyze:v1", code)

    expected_digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    assert key == f"ai-assistant:v2:analyze:v1:{expected_digest}"


def test_cache_key_does_not_use_md5():
    """Ensure the generated key does NOT match an MD5-based key."""
    code = "python\nprint('hello')"

    key = AppCache()._make_key("analyze:v1", code)

    md5_digest = hashlib.md5(code.encode("utf-8")).hexdigest()
    assert md5_digest not in key
