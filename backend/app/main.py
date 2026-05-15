"""
QyverixAI — AI Developer Assistant Backend
FastAPI application entry point
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import time
import uuid
import os
import logging

from app.routers import explanation, debugging, suggestions, analyze

# ── Logging ──
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("qyverix")

# ── App ──
app = FastAPI(
    title="QyverixAI",
    description="Open-source AI Developer Assistant - code explanation, debugging, and improvement suggestions.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID + Timing Middleware ──
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration}ms"
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} → {response.status_code} ({duration}ms)"
    )
    return response


# ── Exception Handler ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again."},
    )


# ── Routers ──
app.include_router(explanation.router, prefix="/explanation", tags=["Explanation"])
app.include_router(debugging.router, prefix="/debugging", tags=["Debugging"])
app.include_router(suggestions.router, prefix="/suggestions", tags=["Suggestions"])
app.include_router(analyze.router, prefix="/analyze", tags=["Full Analysis"])

# ── Serve frontend if built ──
# Try multiple possible paths (backend Dockerfile vs root Dockerfile context)
possible_frontends = [
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
    ),  # backend/Dockerfile build
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "frontend")
    ),  # root Dockerfile build
    "/app/frontend",  # root Dockerfile explicit
]
FRONTEND_PATH = None
for path in possible_frontends:
    if os.path.isdir(path):
        FRONTEND_PATH = path
        logger.info(f"Frontend mounted from: {FRONTEND_PATH}")
        app.mount(
            "/app", StaticFiles(directory=FRONTEND_PATH, html=True), name="frontend"
        )
        break
if not FRONTEND_PATH:
    logger.warning(f"Frontend directory not found. Checked: {possible_frontends}")


# ── Root ──
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/app/")


@app.get("/ping", tags=["System"])
def ping():
    return {"message": "pong"}


# ── Health ──
@app.get("/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "provider": os.getenv("AI_PROVIDER", "rule-based"),
        "llm_enabled": os.getenv("LLM_ENABLED", "false").lower() == "true",
    }


# ── Info ──
@app.get("/info", tags=["System"])
def info():
    return {
        "name": "QyverixAI",
        "description": "Open-source AI Developer Assistant",
        "endpoints": ["/explanation/", "/debugging/", "/suggestions/", "/analyze/"],
        "docs": "/docs",
        "github": "https://github.com/imDarshanGK/AI-dev-assistant",
    }
