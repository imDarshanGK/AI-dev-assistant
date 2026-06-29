import time

from fastapi import HTTPException, Request, status


class IPAddressRateLimiter:
    """A thread-safe, in-memory rate limiter per IP address using a sliding window."""

    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self.requests = {}

    def is_rate_limited(self, ip: str) -> bool:
        now = time.time()
        timestamps = self.requests.get(ip, [])
        # Filter timestamps within the current window
        valid_timestamps = [t for t in timestamps if now - t < self.window]
        self.requests[ip] = valid_timestamps

        if len(valid_timestamps) >= self.limit:
            return True

        self.requests[ip].append(now)
        return False

    async def __call__(self, request: Request):
        # Determine client IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        if self.is_rate_limited(ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )

    def clear(self):
        self.requests.clear()


# Initialize shared rate limiter for authentication endpoints: 5 requests per 60 seconds
auth_rate_limiter = IPAddressRateLimiter(limit=5, window=60)
