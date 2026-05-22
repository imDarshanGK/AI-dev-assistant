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
from contextlib import asynccontextmanager

from .routers import explanation, debugging, suggestions, analyze, subscribe
from .services.scheduler import start_scheduler, stop_scheduler
from .services.rate_limiter import RateLimiter
from .config import settings
from .schemas import HealthResponse



# ── Rate limiter (distributed, with Redis fallback) ────────────────────────────
rate_limiter: RateLimiter | None = None


def rate_limit_headers(limit: int, remaining: int) -> dict[str, str]:
    """Build rate limit headers for API responses."""
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(remaining, 0)),
    }


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global rate_limiter
    print("🚀 QyverixAI backend starting…")
    rate_limiter = RateLimiter(settings)
    print(f"   Rate limiter backend: {rate_limiter.get_backend()}")
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
    client_ip = request.client.host if request.client else "unknown"

    # Extract real IP from X-Forwarded-For if behind proxy
    if rate_limiter:
        headers_dict = dict(request.headers)
        client_ip = rate_limiter.extract_ip(headers_dict, client_ip)

    remaining = settings.rate_limit_per_minute

    # Apply rate limiting to analysis endpoints only
    if request.url.path in ("/explanation/", "/debugging/", "/suggestions/", "/analyze/"):
        if rate_limiter:
            allowed, remaining = rate_limiter.check_limit(client_ip)
            if not allowed:
                elapsed = (time.perf_counter() - start) * 1000
                headers = rate_limit_headers(settings.rate_limit_per_minute, 0)
                headers["Retry-After"] = str(settings.rate_limit_window_seconds)
                headers["X-Process-Time-Ms"] = f"{elapsed:.2f}"
                headers["X-QyverixAI-Version"] = "3.0.0"
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Rate limit exceeded. Max {settings.rate_limit_per_minute} requests/minute."
                    },
                    headers=headers,
                )

    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    response.headers.update(rate_limit_headers(settings.rate_limit_per_minute, remaining))
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
app.include_router(debugging.router,   prefix="/debugging",   tags=["Debugging"])
app.include_router(suggestions.router, prefix="/suggestions", tags=["Suggestions"])
app.include_router(analyze.router,     prefix="/analyze",     tags=["Full Analysis"])
app.include_router(subscribe.router,   prefix="/subscribe",   tags=["Subscription"])


# ── Core Endpoints ────────────────────────────────────────────────────────────
@app.get("/", response_model=HealthResponse, tags=["System"])
async def root():
    return {
        "status": "ok",
        "version": "3.0.0",
        "message": "QyverixAI API is running.",
        "endpoints": ["/explanation/", "/debugging/", "/suggestions/", "/analyze/"],
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "version": "3.0.0",
        "message": "QyverixAI is healthy",
        "endpoints": ["/explanation/", "/debugging/", "/suggestions/", "/analyze/"],
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
