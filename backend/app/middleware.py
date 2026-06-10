import logging
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse

from .config import settings

try:
    from fastapi_limiter import FastAPILimiter
    from fastapi_limiter.depends import RateLimiter
except ImportError:
    FastAPILimiter = None
    RateLimiter = None

logger = logging.getLogger("ai_assistant.api")

_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = Lock()


def get_client_key(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if xff:
        return xff
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def request_id_and_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    started_at = time.perf_counter()
    logger.info(
        "request_started request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )

    response = await call_next(request)

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_finished request_id=%s method=%s path=%s status=%s elapsed_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


async def request_size_limit_middleware(request: Request, call_next):
    if request.method not in {"POST", "PUT", "PATCH"}:
        return await call_next(request)

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
            if declared_size > settings.max_request_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "payload_too_large",
                        "detail": f"Request body exceeds {settings.max_request_bytes} bytes limit.",
                    },
                )
        except ValueError:
            pass

    return await call_next(request)


async def dynamic_rate_limiter(request: Request, response: Response):
    """
    Dynamic dependency that checks if Redis-backed rate limiter is initialized.
    If so, it uses it. Otherwise, it gracefully falls back to the in-memory deque.
    """
    if (
        FastAPILimiter is not None
        and getattr(FastAPILimiter, "redis", None) is not None
    ):
        try:
            limiter = RateLimiter(
                times=settings.rate_limit_requests,
                seconds=settings.rate_limit_window_seconds,
            )
            await limiter(request=request, response=response)
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(
                f"Redis rate limiting failed: {e}. Falling back to in-memory."
            )

    # In-memory fallback
    client_key = get_client_key(request)
    now = time.time()
    cutoff = now - settings.rate_limit_window_seconds

    with _rate_limit_lock:
        bucket = _rate_limit_buckets[client_key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= settings.rate_limit_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {settings.rate_limit_requests} requests/{settings.rate_limit_window_seconds}s.",
            )

        bucket.append(now)
