"""Distributed rate limiting with optional Redis backend."""

from __future__ import annotations
import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Settings

log = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with dual-backend support (memory + Redis)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.window_seconds = settings.rate_limit_window_seconds
        self.limit_per_minute = settings.rate_limit_per_minute
        self.backend_name = "memory"

        # Memory backend (always available as fallback)
        self._request_counts: dict[str, list[float]] = defaultdict(list)
        self._redis_client = None

        # Initialize Redis if configured
        if settings.redis_url and settings.rate_limiter_backend != "memory":
            try:
                import redis
                self._redis_client = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=False,
                    socket_connect_timeout=3,
                    socket_keepalive=True,
                )
                # Test connection
                self._redis_client.ping()
                self.backend_name = "redis"
                log.info("rate_limiter_backend=redis")
            except Exception as exc:
                log.warning(
                    "Failed to initialize Redis for rate limiting, falling back to memory. error=%s",
                    str(exc),
                )
                self._redis_client = None
        elif settings.rate_limiter_backend == "redis" and not settings.redis_url:
            log.error("RATE_LIMITER_BACKEND=redis but REDIS_URL not set")
            raise ValueError("RATE_LIMITER_BACKEND=redis requires REDIS_URL")

    def check_limit(self, ip: str) -> tuple[bool, int]:
        """
        Check if IP has exceeded rate limit.

        Returns: (allowed: bool, remaining: int)
        - allowed=True: Request can proceed, remaining=quota left
        - allowed=False: Request blocked, remaining=0
        """
        if self._redis_client and self.backend_name == "redis":
            return self._check_redis(ip)
        return self._check_memory(ip)

    def _check_memory(self, ip: str) -> tuple[bool, int]:
        """In-memory sliding window rate limiter."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Remove expired requests
        self._request_counts[ip] = [t for t in self._request_counts[ip] if t > cutoff]

        # Check limit
        current_count = len(self._request_counts[ip])
        if current_count >= self.limit_per_minute:
            return False, 0  # Blocked

        # Record request
        self._request_counts[ip].append(now)
        remaining = self.limit_per_minute - len(self._request_counts[ip])
        return True, remaining

    def _check_redis(self, ip: str) -> tuple[bool, int]:
        """Redis ZSET-based distributed rate limiter."""
        try:
            key = f"rl:ip:{ip}"
            now = time.time()
            cutoff = now - self.window_seconds

            # Add current request timestamp
            self._redis_client.zadd(key, {str(now): now})

            # Count requests in current window
            count = self._redis_client.zcount(key, cutoff, now)

            # Set expiration to window size
            self._redis_client.expire(key, self.window_seconds + 1)

            if count > self.limit_per_minute:
                return False, 0  # Blocked

            remaining = self.limit_per_minute - count
            return True, remaining
        except Exception as exc:
            log.warning("Redis rate limit check failed, falling back to memory. error=%s", str(exc))
            # Graceful fallback to memory
            return self._check_memory(ip)

    def extract_ip(self, request_headers: dict[str, str], client_host: str | None) -> str:
        """
        Extract client IP from request, respecting X-Forwarded-For header.

        Useful for deployments behind proxies/load balancers.
        """
        # Check for X-Forwarded-For (first IP is the original client)
        forwarded_for = request_headers.get("X-Forwarded-For", "").strip()
        if forwarded_for:
            # Take first IP, ignore rest
            ips = [ip.strip() for ip in forwarded_for.split(",")]
            if ips and ips[0]:
                return ips[0]

        # Fallback to direct client IP
        return client_host or "unknown"

    def get_backend(self) -> str:
        """Return current backend name."""
        return self.backend_name

    def reset(self) -> None:
        """Reset rate limiter state (useful for testing)."""
        self._request_counts.clear()
        if self._redis_client:
            try:
                # Clean up Redis keys
                for key in self._redis_client.scan_iter("rl:ip:*"):
                    self._redis_client.delete(key)
            except Exception as exc:
                log.warning("Failed to reset Redis rate limiter. error=%s", str(exc))
