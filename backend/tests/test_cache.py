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
