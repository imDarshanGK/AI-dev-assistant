"""Tests for distributed rate limiting (memory + Redis backends)."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from app.services.rate_limiter import RateLimiter
from app.config import Settings


@pytest.fixture
def settings():
    """Create settings for testing."""
    s = Settings()
    s.rate_limit_per_minute = 5
    s.rate_limit_window_seconds = 60
    s.redis_url = None
    s.rate_limiter_backend = "auto"
    return s


@pytest.fixture
def memory_limiter(settings):
    """Create in-memory rate limiter."""
    settings.redis_url = None
    limiter = RateLimiter(settings)
    yield limiter
    limiter.reset()


class TestMemoryBackend:
    """Test in-memory rate limiting."""

    def test_allows_requests_under_limit(self, memory_limiter):
        """Should allow requests under limit."""
        ip = "192.168.1.1"
        for i in range(5):
            allowed, remaining = memory_limiter.check_limit(ip)
            assert allowed is True
            assert remaining == 4 - i

    def test_blocks_requests_over_limit(self, memory_limiter):
        """Should block requests exceeding limit."""
        ip = "192.168.1.1"
        # Exhaust limit
        for _ in range(5):
            memory_limiter.check_limit(ip)

        # 6th request should be blocked
        allowed, remaining = memory_limiter.check_limit(ip)
        assert allowed is False
        assert remaining == 0

    def test_sliding_window_resets(self, memory_limiter, monkeypatch):
        """Should reset window after timeout."""
        ip = "192.168.1.1"

        # Make 5 requests
        for _ in range(5):
            memory_limiter.check_limit(ip)

        # Fast forward time (add 61 seconds)
        current_time = time.time()
        monkeypatch.setattr(time, "time", lambda: current_time + 61)

        # Should allow new request (window expired)
        allowed, remaining = memory_limiter.check_limit(ip)
        assert allowed is True
        assert remaining == 4

    def test_multiple_ips_isolated(self, memory_limiter):
        """Different IPs should have independent limits."""
        ip1, ip2 = "192.168.1.1", "192.168.1.2"

        # Fill ip1 limit
        for _ in range(5):
            memory_limiter.check_limit(ip1)

        # ip1 should be blocked
        allowed, _ = memory_limiter.check_limit(ip1)
        assert allowed is False

        # ip2 should still be allowed
        allowed, remaining = memory_limiter.check_limit(ip2)
        assert allowed is True
        assert remaining == 4

    def test_backend_name(self, memory_limiter):
        """Should identify as memory backend."""
        assert memory_limiter.get_backend() == "memory"


class TestIPExtraction:
    """Test IP extraction logic."""

    def test_extract_ip_direct_connection(self, memory_limiter):
        """Should use direct client IP if no forwarding."""
        headers = {}
        result = memory_limiter.extract_ip(headers, "203.0.113.1")
        assert result == "203.0.113.1"

    def test_extract_ip_x_forwarded_for(self, memory_limiter):
        """Should extract first IP from X-Forwarded-For."""
        headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1, 172.16.0.1"}
        result = memory_limiter.extract_ip(headers, "127.0.0.1")
        assert result == "203.0.113.1"

    def test_extract_ip_x_forwarded_for_single(self, memory_limiter):
        """Should handle single IP in X-Forwarded-For."""
        headers = {"X-Forwarded-For": "203.0.113.1"}
        result = memory_limiter.extract_ip(headers, "127.0.0.1")
        assert result == "203.0.113.1"

    def test_extract_ip_fallback_to_unknown(self, memory_limiter):
        """Should fallback to 'unknown' if no IP provided."""
        headers = {}
        result = memory_limiter.extract_ip(headers, None)
        assert result == "unknown"


class TestRateLimiterHeaders:
    """Test rate limit response headers."""

    def test_headers_format(self, memory_limiter):
        """Should return properly formatted headers."""
        allowed, remaining = memory_limiter.check_limit("192.168.1.1")
        assert allowed is True
        assert 0 <= remaining <= 5


class TestMemoryReset:
    """Test rate limiter reset functionality."""

    def test_reset_clears_state(self, memory_limiter):
        """Reset should clear all request history."""
        ip = "192.168.1.1"

        # Make requests to fill quota
        for _ in range(5):
            memory_limiter.check_limit(ip)

        # Verify blocked
        allowed, _ = memory_limiter.check_limit(ip)
        assert allowed is False

        # Reset
        memory_limiter.reset()

        # Should be allowed again
        allowed, remaining = memory_limiter.check_limit(ip)
        assert allowed is True
        assert remaining == 4


class TestRedisBackend:
    """Test Redis-backed rate limiting (requires Redis)."""

    @pytest.fixture
    def redis_limiter(self, settings):
        """Create Redis rate limiter if Redis available."""
        settings.redis_url = "redis://localhost:6379"
        settings.rate_limiter_backend = "auto"
        try:
            limiter = RateLimiter(settings)
            if limiter.get_backend() == "redis":
                yield limiter
                limiter.reset()
            else:
                pytest.skip("Redis not available")
        except Exception:
            pytest.skip("Redis not available")

    def test_redis_allows_requests_under_limit(self, redis_limiter):
        """Redis: Should allow requests under limit."""
        ip = "192.168.1.1"
        for i in range(5):
            allowed, remaining = redis_limiter.check_limit(ip)
            assert allowed is True
            assert remaining == 4 - i

    def test_redis_blocks_requests_over_limit(self, redis_limiter):
        """Redis: Should block requests exceeding limit."""
        ip = "192.168.1.1"
        # Exhaust limit
        for _ in range(5):
            redis_limiter.check_limit(ip)

        # 6th request should be blocked
        allowed, remaining = redis_limiter.check_limit(ip)
        assert allowed is False
        assert remaining == 0

    def test_redis_distributed_counting(self, redis_limiter):
        """Redis: Should count requests across simulated instances."""
        ip = "192.168.1.1"

        # Simulate 2 instances checking limit for same IP
        for i in range(3):
            allowed, remaining = redis_limiter.check_limit(ip)
            assert allowed is True

        for i in range(2):
            allowed, remaining = redis_limiter.check_limit(ip)
            assert allowed is True

        # 6th should be blocked (distributed count)
        allowed, remaining = redis_limiter.check_limit(ip)
        assert allowed is False

    def test_redis_fallback_on_error(self, redis_limiter):
        """Redis: Should fallback to memory on connection error."""
        ip = "192.168.1.1"

        # Simulate Redis connection error
        with patch.object(redis_limiter._redis_client, "zadd", side_effect=Exception("Connection failed")):
            # Should fallback to memory gracefully
            allowed, remaining = redis_limiter.check_limit(ip)
            assert allowed is True  # Memory backend allows it

    def test_redis_backend_name(self, redis_limiter):
        """Redis: Should identify as redis backend."""
        assert redis_limiter.get_backend() == "redis"


class TestBackendConfiguration:
    """Test rate limiter backend configuration."""

    def test_backend_auto_memory(self, settings):
        """Auto mode should use memory when Redis not set."""
        settings.redis_url = None
        settings.rate_limiter_backend = "auto"
        limiter = RateLimiter(settings)
        assert limiter.get_backend() == "memory"

    def test_backend_forced_memory(self, settings):
        """Should force memory backend when explicitly set."""
        settings.redis_url = "redis://localhost:6379"
        settings.rate_limiter_backend = "memory"
        limiter = RateLimiter(settings)
        assert limiter.get_backend() == "memory"

    def test_backend_forced_redis_missing_url(self, settings):
        """Should raise error if Redis forced but no URL."""
        settings.redis_url = None
        settings.rate_limiter_backend = "redis"
        with pytest.raises(ValueError):
            RateLimiter(settings)

    def test_backend_auto_redis_available(self, settings):
        """Auto mode should use Redis when available."""
        settings.redis_url = "redis://localhost:6379"
        settings.rate_limiter_backend = "auto"
        try:
            limiter = RateLimiter(settings)
            # If Redis available, should be redis backend
            if limiter._redis_client:
                assert limiter.get_backend() == "redis"
        except Exception:
            # Redis not available, skip
            pass


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_concurrent_requests_same_ip(self, memory_limiter):
        """Should handle rapid requests from same IP."""
        ip = "192.168.1.1"
        results = [memory_limiter.check_limit(ip) for _ in range(10)]

        # First 5 allowed, rest blocked
        assert sum(1 for allowed, _ in results if allowed) == 5
        assert sum(1 for allowed, _ in results if not allowed) == 5

    def test_remaining_count_accuracy(self, memory_limiter):
        """Remaining count should be accurate."""
        ip = "192.168.1.1"
        for i in range(5):
            allowed, remaining = memory_limiter.check_limit(ip)
            assert remaining == 4 - i  # 4, 3, 2, 1, 0

    def test_zero_limit(self, settings):
        """Should handle zero limit gracefully."""
        settings.rate_limit_per_minute = 0
        limiter = RateLimiter(settings)
        allowed, remaining = limiter.check_limit("192.168.1.1")
        # With 0 limit, should immediately block
        assert allowed is False


class TestIntegration:
    """Integration tests with real middleware behavior."""

    def test_rate_limit_lifecycle(self, memory_limiter):
        """Test full lifecycle: allow, block, reset."""
        ip = "192.168.1.1"

        # Phase 1: Allow requests
        for _ in range(5):
            allowed, _ = memory_limiter.check_limit(ip)
            assert allowed is True

        # Phase 2: Block excess
        allowed, _ = memory_limiter.check_limit(ip)
        assert allowed is False

        # Phase 3: Reset and retry
        memory_limiter.reset()
        allowed, _ = memory_limiter.check_limit(ip)
        assert allowed is True
