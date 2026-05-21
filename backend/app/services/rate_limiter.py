import os
import time
import redis
from typing import Optional

# Redis connection (falls back to in-memory if Redis not available)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

_redis_client: Optional[redis.Redis] = None

def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            client = redis.from_url(REDIS_URL, decode_responses=True)
            client.ping()
            _redis_client = client
        except Exception:
            _redis_client = None
    return _redis_client


class RateLimiter:
    """
    Distributed rate limiter using Redis (sliding window).
    Falls back to in-memory if Redis is unavailable.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._memory_store: dict = {}  # fallback

    def _check_redis(self, key: str) -> tuple[Optional[bool], int]:
        client = get_redis_client()
        if client is None:
            return None, 0

        try:
            now = time.time()
            window_start = now - self.window_seconds
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, self.window_seconds)
            results = pipe.execute()
            request_count = results[2]
            remaining = max(0, self.max_requests - request_count)
            allowed = request_count <= self.max_requests
            return allowed, remaining
        except Exception:
            return None, 0

    def _check_memory(self, key: str) -> tuple[bool, int]:
        now = time.time()
        window_start = now - self.window_seconds
        timestamps = self._memory_store.get(key, [])
        timestamps = [t for t in timestamps if t > window_start]
        timestamps.append(now)
        self._memory_store[key] = timestamps
        count = len(timestamps)
        remaining = max(0, self.max_requests - count)
        allowed = count <= self.max_requests
        return allowed, remaining

    def is_allowed(self, identifier: str) -> tuple[bool, int]:
        """
        Check if the request is allowed.
        Returns (allowed: bool, remaining: int)
        """
        key = f"rate_limit:{identifier}"
        allowed, remaining = self._check_redis(key)
        if allowed is None:
            allowed, remaining = self._check_memory(key)
        return allowed, remaining


# Default limiter instance
default_limiter = RateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_REQUESTS", 10)),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", 60)),
)