"""
QyverixAI — Backend API
FastAPI application with advanced middleware, rate limiting, and full analysis engine.
"""

from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .limiter import limiter
import os
import logging
from contextlib import asynccontextmanager

from .routers import (
    analyze,
    auth,
    chat,
    debugging,
    explanation,
    history,
    share,
    subscribe,
    suggestions,
    upload_file,
    user_data,
)
from .services import database
from .services.scheduler import start_scheduler, stop_scheduler
from .database import Base, engine

from .schemas import HealthResponse


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    print("🚀 QyverixAI backend starting…")
    logging.getLogger(__name__).info("🚀 QyverixAI backend starting…")
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    stop_scheduler()
    logging.getLogger(__name__).info("🛑 QyverixAI backend shutting down…")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="QyverixAI",
    description="AI-powered developer assistant — code explanation, debugging, and improvement.",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

app.add_middleware(SlowAPIMiddleware)

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
app.include_router(history.router,     prefix="/history",     tags=["History"])
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(share.router)
app.include_router(user_data.router)
app.include_router(upload_file.router, prefix="/upload",      tags=['Upload File'] )


# ── Core Endpoints ────────────────────────────────────────────────────────────
@app.get("/", response_model=HealthResponse, tags=["System"])
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
            "/analyze/zip/",
            "/subscribe/",
            "/share/",
            "/history/",
        ],
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
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
            "/analyze/zip/",
            "/subscribe/",
            "/share/",
            "/history/",
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
    logging.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )
