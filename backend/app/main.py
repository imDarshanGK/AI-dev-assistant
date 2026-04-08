from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Request
from fastapi.staticfiles import StaticFiles

from pathlib import Path

import logging

from app.middleware import (
    rate_limit_middleware,
    request_id_and_logging_middleware,
    request_size_limit_middleware,
)
from app.config import settings
from app.database import Base, engine
from app import models  # noqa: F401 - imports models for table registration
from app.services.cache import cache
from app.services.error_tracking import init_error_tracking
from app.routers import analyze, auth, debugging, explanation, suggestions, user_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ai_assistant.api")
init_error_tracking()

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
FRONTEND_AVAILABLE = FRONTEND_DIR.exists() and (FRONTEND_DIR / "index.html").exists()

app = FastAPI(
    title="AI Developer Assistant API",
    description="A beginner-friendly API to explain code, detect issues, and suggest improvements.",
    version="1.0.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(rate_limit_middleware)
app.middleware("http")(request_size_limit_middleware)
app.middleware("http")(request_id_and_logging_middleware)

if FRONTEND_AVAILABLE:
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": jsonable_encoder(exc.errors()),
            "request_id": request_id,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "detail": exc.detail,
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception("unhandled_exception request_id=%s", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "Something went wrong while processing the request.",
            "request_id": request_id,
        },
    )

# Include routers
app.include_router(explanation.router)
app.include_router(debugging.router)
app.include_router(suggestions.router)
app.include_router(analyze.router)
app.include_router(auth.router)
app.include_router(user_data.router)

@app.get("/ping", tags=["Test"])
def ping():
    """Sample test endpoint to check API status."""
    return {"message": "pong"}


@app.get("/health", tags=["Test"])
def health():
    """Health endpoint for uptime checks."""
    return {"status": "ok", "cache_backend": cache.backend}
    
@app.get("/", tags=["Root"])
def root():
    """Open the frontend app when available; otherwise return API status."""
    if FRONTEND_AVAILABLE:
        return RedirectResponse(url="/app/")

    payload = {
        "message": "AI Developer Assistant API is running.",
        "status": "ok",
    }

    if settings.public_root_info and settings.enable_docs:
        payload["docs"] = "/docs"

    return payload
