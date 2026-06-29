"""
QyverixAI — Backend API
FastAPI application with advanced middleware, rate limiting, and full analysis engine.
"""

import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .observability import initialise_app_info, prometheus_metrics_middleware
from .routers import (
    admin,
    analyze,
    auth,
    chat,
    collaboration,
    debugging,
    diagnostics,
    explanation,
)
from .routers import health as health_router
from .routers import history
from .routers import metrics as metrics_router
from .routers import share, subscribe, suggestions, upload_file, user_data
from .schemas import HealthResponse
from .services import database
from .services.scheduler import start_scheduler, stop_scheduler

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


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    print("🚀 QyverixAI backend starting…")
    initialise_app_info(
        version="3.0.0", ai_provider=os.getenv("AI_PROVIDER", "rule-based")
    )
    start_scheduler()
    yield
    stop_scheduler()
    logging.getLogger(__name__).info("🛑 QyverixAI backend shutting down…")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="QyverixAI",
    description="""
## AI-Powered Developer Assistant

Paste any code snippet and instantly receive three analyses:

- 🔍 **Explain** — language detection, plain-English summary, complexity estimate, function and class inventory
- 🐛 **Debug** — 40+ static-analysis pattern checks across 5 languages with exact line numbers, code snippets, and fix suggestions
- ✨ **Improve** — documentation gaps, error handling, type safety — plus a **0–100 quality score** and letter grade **A–F**

**No account required. No API key needed. Works fully offline.**

---

### Supported Languages
`Python` · `JavaScript` · `TypeScript` · `Java` · `C++`

### Rate Limiting
Analysis endpoints are limited to **30 requests / minute per IP** (configurable via `RATE_LIMIT_PER_MINUTE`).
Responses include `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers.
A `429` response includes a `Retry-After` header indicating seconds to wait.

### Authentication
Protected endpoints use **JWT Bearer tokens**.
Obtain a token via `POST /auth/login` and pass it as `Authorization: Bearer <token>`.
    """,
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    contact={
        "name": "Darshan G K",
        "url": "https://github.com/imDarshanGK/AI-dev-assistant",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "Explanation",
            "description": "Plain-English breakdown of what a piece of code does — language, summary, complexity, and structure.",
        },
        {
            "name": "Debugging",
            "description": "Static-analysis bug detection across 5 languages. Returns exact line numbers, code snippets, and fix suggestions.",
        },
        {
            "name": "Suggestions",
            "description": "Improvement recommendations covering docs, error handling, type safety, and testing — with a 0–100 quality score and A–F grade.",
        },
        {
            "name": "Full Analysis",
            "description": "Runs Explanation + Debugging + Suggestions in a single request with combined timing metrics.",
        },
        {
            "name": "Auth",
            "description": "User signup, login, and current-user profile (`/auth/signup`, `/auth/login`, `/auth/me`).",
        },
        {
            "name": "Share",
            "description": "Create short-lived share links (7-day TTL) for any analysis result and load them back by ID.",
        },
        {
            "name": "History",
            "description": "Per-user analysis history — stores the last 50 analyses. Requires authentication.",
        },
        {
            "name": "Upload File",
            "description": "Drag-and-drop or programmatic file upload. Accepts `.py`, `.js`, `.ts`, `.java`, `.cpp`.",
        },
        {
            "name": "Subscription",
            "description": "Email newsletter subscription and unsubscription.",
        },
        {
            "name": "Admin",
            "description": "Administrator-only operations (user role management, account deletion) and a queryable, append-only audit log of privileged actions.",
        },
        {
            "name": "System",
            "description": "Root info, legacy health check, and ping endpoints.",
        },
    ],
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

app.middleware("http")(prometheus_metrics_middleware)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    ip = request.client.host if request.client else "unknown"
    remaining = RATE_LIMIT

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


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(explanation.router, prefix="/explanation", tags=["Explanation"])
app.include_router(debugging.router, prefix="/debugging", tags=["Debugging"])
app.include_router(suggestions.router, prefix="/suggestions", tags=["Suggestions"])
app.include_router(analyze.router, prefix="/analyze", tags=["Full Analysis"])
app.include_router(subscribe.router, prefix="/subscribe", tags=["Subscription"])
app.include_router(history.router, prefix="/history", tags=["History"])
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(share.router)
app.include_router(user_data.router)
app.include_router(admin.router)
app.include_router(upload_file.router, prefix="/upload", tags=["Upload File"])
app.include_router(
    collaboration.router,
    prefix="/collaboration",
    tags=["Collaboration"],
)

app.include_router(health_router.router)
app.include_router(metrics_router.router)
app.include_router(diagnostics.router)


# ── Core Endpoints ────────────────────────────────────────────────────────────
@app.get(
    "/",
    response_model=HealthResponse,
    tags=["System"],
    summary="API root — service info",
    description="Returns the current API version, status, and a list of all available endpoint paths.",
)
async def root():
    return {
        "status": "ok",
        "version": "3.0.0",
        "message": "QyverixAI API is running.",
        "endpoints": [
            "/auth/signup",
            "/auth/login",
            "/auth/me",
            "/explanation/",
            "/debugging/",
            "/suggestions/",
            "/analyze/",
            "/subscribe/",
            "/share/",
            "/auth/",
            "/chat/",
            "/user/",
            "/analyze/zip/",
            "/history/",
            "/collaboration/ws/{session_id}",
        ],
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Legacy health check",
    description=(
        "Retained for backwards compatibility. Returns a simple `ok` status. "
        "For production liveness/readiness probes use `/healthz/live` and `/healthz/ready` instead."
    ),
)
async def health_check():
    return {
        "status": "ok",
        "version": "3.0.0",
        "message": "QyverixAI is healthy",
        "endpoints": [
            "/auth/signup",
            "/auth/login",
            "/auth/me",
            "/explanation/",
            "/debugging/",
            "/suggestions/",
            "/analyze/",
            "/subscribe/",
            "/share/",
            "/auth/",
            "/chat/",
            "/user/",
            "/analyze/zip/",
            "/history/",
            "/collaboration/ws/{session_id}",
        ],
    }


@app.get(
    "/ping",
    tags=["System"],
    summary="Ping — connection test",
    description='Lightweight endpoint to verify the server is reachable. Returns `{"message": "pong"}`.',
)
async def ping():
    return {"message": "pong"}


# ── Static / Frontend ─────────────────────────────────────────────────────────
_frontend = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(_frontend):
    app.mount("/app", StaticFiles(directory=_frontend, html=True), name="frontend")


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )
