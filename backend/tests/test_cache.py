import hashlib
import pytest
import time

from app.services.cache import AppCache
from app.config import settings

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

@pytest.fixture
def memory_cache():
    original_url = settings.redis_url
    settings.redis_url = None
    cache = AppCache()
    settings.redis_url = original_url
    return cache

def test_cache_set_and_get_success(memory_cache):
    settings.cache_enabled = True
    settings.cache_ttl_seconds = 60
    
    memory_cache.set("test_namespace", "my_code", {"data": "success"})
    result = memory_cache.get("test_namespace", "my_code")
    
    assert result is not None
    assert result["data"] == "success"

def test_cache_disabled_returns_none(memory_cache):
    settings.cache_enabled = False
    
    memory_cache.set("disabled_ns", "code123", {"data": "hidden"})
    result = memory_cache.get("disabled_ns", "code123")
    
    assert result is None

def test_cache_expiration(memory_cache):
    settings.cache_enabled = True
    settings.cache_ttl_seconds = -1
    
    memory_cache.set("expire_ns", "code123", {"data": "gone"})
    result = memory_cache.get("expire_ns", "code123")
    
    assert result is None
