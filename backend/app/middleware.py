import logging
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import settings

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
                    "detail": (
                        f"Too many requests. Limit is {settings.rate_limit_requests} requests "
                        f"per {settings.rate_limit_window_seconds} seconds."
                    ),
                },
            )

        bucket.append(now)

    return await call_next(request)


async def static_cache_headers_middleware(request: Request, call_next):
    """Add Cache-Control headers for static frontend assets (Issue #533).

    Only affects responses served under the /app mount (FastAPI StaticFiles).
    Cache durations are intentionally conservative because frontend filenames
    are NOT content-hashed, so immutable/long-lived caching would serve stale
    assets after a deployment.

    Strategy by asset type:
    - HTML / directory roots  → no-cache, must-revalidate
      Always revalidate so the latest app shell is fetched after each deploy.
    - JS / CSS                → public, max-age=3600  (1 hour)
      Short window to limit stale-asset exposure without hammering the server.
    - Images / favicon        → public, max-age=86400  (24 hours)
      Visuals change rarely between deploys; a day-long cache is safe.
    - Web fonts               → public, max-age=604800  (7 days)
      Fonts almost never change; a week avoids needless redownloads.
    """
    response = await call_next(request)

    path = request.url.path

    # Only apply to the static frontend mount; leave API routes untouched.
    if not path.startswith("/app"):
        return response

    if path.endswith((".woff", ".woff2", ".ttf", ".eot", ".otf")):
        # Web fonts — 7 days
        response.headers["Cache-Control"] = "public, max-age=604800"
    elif path.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")):
        # Images and favicon — 24 hours
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif path.endswith((".js", ".css")):
        # JavaScript and CSS — 1 hour
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        # HTML files and bare directory paths — always revalidate
        response.headers["Cache-Control"] = "no-cache, must-revalidate"

    return response
