"""
QyverixAI — Backend API
FastAPI application with advanced middleware, rate limiting, and full analysis engine.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import time
import os
from collections import defaultdict
from contextlib import asynccontextmanager


from .routers import explanation, debugging, suggestions, analyze, subscribe, share
from .services.scheduler import start_scheduler, stop_scheduler

from .schemas import HealthResponse

# ── Rate limiter (in-memory, per IP) ──────────────────────────────────────────
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
RATE_LIMIT_WINDOW_SECONDS = 60
_request_counts: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(ip: str) -> int:
    """Record a request and return the remaining requests in the current window."""
    now = time.time()
    _request_counts[ip] = [
        t for t in _request_counts[ip] if now - t < RATE_LIMIT_WINDOW_SECONDS
    ]
    if len(_request_counts[ip]) >= RATE_LIMIT:
        return -1
    _request_counts[ip].append(now)
    return RATE_LIMIT - len(_request_counts[ip])


def rate_limit_headers(remaining: int) -> dict[str, str]:
    """Build rate limit headers for API responses."""
    return {
        "X-RateLimit-Limit": str(RATE_LIMIT),
        "X-RateLimit-Remaining": str(max(remaining, 0)),
    }


# ── Upload size limit ────────────────────────────────────────────────────────
MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", "1048576"))

# Endpoints that accept request bodies and should be size-gated.
_SIZE_GATED_PATHS: set[str] = {
    "/explanation/",
    "/debugging/",
    "/suggestions/",
    "/analyze/",
}


def _payload_too_large_response(limit: int) -> JSONResponse:
    """Return a 413 JSON response with the configured limit expressed in KB."""
    limit_kb = limit // 1024
    return JSONResponse(
        status_code=413,
        content={
            "detail": f"Payload too large. Maximum allowed size is {limit_kb} KB."
        },
    )


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 QyverixAI backend starting…")
    start_scheduler()
    yield
    stop_scheduler()
    print("🛑 QyverixAI backend shutting down…")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="QyverixAI",
    description="AI-powered developer assistant — code explanation, debugging, and improvement.",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    ip = request.client.host if request.client else "unknown"
    remaining = RATE_LIMIT

    # Apply rate limiting to analysis endpoints only
    if request.url.path in (
        "/explanation/",
        "/debugging/",
        "/suggestions/",
        "/analyze/",
    ):
        remaining = check_rate_limit(ip)
        if remaining < 0:
            elapsed = (time.perf_counter() - start) * 1000
            headers = rate_limit_headers(0)
            headers["Retry-After"] = str(RATE_LIMIT_WINDOW_SECONDS)
            headers["X-Process-Time-Ms"] = f"{elapsed:.2f}"
            headers["X-QyverixAI-Version"] = "3.0.0"
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Max {RATE_LIMIT} requests/minute."
                },
                headers=headers,
            )

    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    response.headers.update(rate_limit_headers(remaining))
    response.headers["X-Process-Time-Ms"] = f"{elapsed:.2f}"
    response.headers["X-QyverixAI-Version"] = "3.0.0"
    return response


@app.middleware("http")
async def add_cache_header(request: Request, call_next):
    response = await call_next(request)

    if request.url.path == "/analyze/" and request.method == "POST":
        response.headers.setdefault("X-Cache", "MISS")

    return response


@app.middleware("http")
async def payload_size_guard(request: Request, call_next):
    """Stream-read the request body, enforce MAX_UPLOAD_SIZE_BYTES, then
    reconstruct the stream so downstream handlers can call request.json()."""

    # Only gate POST/PUT/PATCH on the analysis endpoints
    if request.method not in {"POST", "PUT", "PATCH"}:
        return await call_next(request)

    if request.url.path not in _SIZE_GATED_PATHS:
        return await call_next(request)

    # Re-read the env var at request time so tests can monkeypatch it.
    limit: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", "1048576"))

    # ── Fast-path: reject immediately when Content-Length is declared ──
    content_length_header = request.headers.get("content-length")
    if content_length_header is not None:
        try:
            declared = int(content_length_header)
            if declared > limit:
                return _payload_too_large_response(limit)
        except ValueError:
            pass  # non-integer header — fall through to streaming check

    # ── Stream-read the body and enforce the byte limit ───────────────
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            return _payload_too_large_response(limit)
        chunks.append(chunk)

    # ── Reconstruct the consumed stream for downstream handlers ───────
    # Setting _body lets Starlette's body()/stream()/json() reuse the
    # cached bytes without hitting the "Stream consumed" RuntimeError.
    request._body = b"".join(chunks)

    return await call_next(request)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(explanation.router, prefix="/explanation", tags=["Explanation"])
app.include_router(debugging.router, prefix="/debugging", tags=["Debugging"])
app.include_router(suggestions.router, prefix="/suggestions", tags=["Suggestions"])
app.include_router(analyze.router, prefix="/analyze", tags=["Full Analysis"])
app.include_router(subscribe.router, prefix="/subscribe", tags=["Subscription"])
app.include_router(share.router)


# ── Core Endpoints ────────────────────────────────────────────────────────────
@app.get("/", response_model=HealthResponse, tags=["System"])
async def root():
    return {
        "status": "ok",
        "version": "3.0.0",
        "message": "QyverixAI API is running.",
        "endpoints": [
            "/explanation/",
            "/debugging/",
            "/suggestions/",
            "/analyze/",
            "/share/",
        ],
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "version": "3.0.0",
        "message": "QyverixAI is healthy",
        "endpoints": [
            "/explanation/",
            "/debugging/",
            "/suggestions/",
            "/analyze/",
            "/share/",
        ],
    }


@app.get("/ping", tags=["System"])
async def ping():
    return {"message": "pong"}


# ── Static / Frontend ─────────────────────────────────────────────────────────
_frontend = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(_frontend):
    app.mount("/app", StaticFiles(directory=_frontend, html=True), name="frontend")


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )
