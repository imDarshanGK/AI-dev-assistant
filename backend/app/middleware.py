import logging
import time
import uuid
from collections import defaultdict, deque
from enum import Enum
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import settings

logger = logging.getLogger("ai_assistant.api")

_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = Lock()


def get_client_key(request: Request) -> str:
    """Extract client IP for rate limiting.

    Only uses X-Forwarded-For if TRUST_PROXY_HEADERS is enabled.
    Falls back to direct connection IP if proxy headers are not trusted.
    """
    if settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
        if xff and xff != "unknown":
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


async def rate_limit_middleware(request: Request, call_next):
    client_key = get_client_key(request)
    now = time.time()
    cutoff = now - settings.rate_limit_window_seconds
    with _rate_limit_lock:
        bucket = _rate_limit_buckets[client_key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "detail": f"Too many requests. Limit is {settings.rate_limit_requests} requests per {settings.rate_limit_window_seconds} seconds.",
                },
            )
        bucket.append(now)
    return await call_next(request)


class ErrorCategory(str, Enum):
    CLIENT = "client_error"
    SERVER = "server_error"
    PROVIDER = "provider_error"


ERROR_CATEGORY_MAP = {
    400: ErrorCategory.CLIENT,
    401: ErrorCategory.CLIENT,
    403: ErrorCategory.CLIENT,
    404: ErrorCategory.CLIENT,
    413: ErrorCategory.CLIENT,
    422: ErrorCategory.CLIENT,
    429: ErrorCategory.CLIENT,
    500: ErrorCategory.SERVER,
    502: ErrorCategory.PROVIDER,
    503: ErrorCategory.PROVIDER,
    504: ErrorCategory.PROVIDER,
}


async def error_classification_middleware(request: Request, call_next):
    response = await call_next(request)
    status = response.status_code
    if status >= 400:
        category = ERROR_CATEGORY_MAP.get(status)
        if category is None:
            category = ErrorCategory.SERVER if status >= 500 else ErrorCategory.CLIENT
        response.headers["X-Error-Category"] = category.value
        logger.warning(
            "error_response request_id=%s status=%s category=%s path=%s",
            getattr(request.state, "request_id", "unknown"),
            status,
            category.value,
            request.url.path,
        )
    return response
