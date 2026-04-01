from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import explanation, debugging, suggestions

app = FastAPI(
    title="AI Developer Assistant API",
    description="A beginner-friendly API to explain code, detect issues, and suggest improvements.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(explanation.router)
app.include_router(debugging.router)
app.include_router(suggestions.router)

@app.get("/ping", tags=["Test"])
def ping():
    """Sample test endpoint to check API status."""
    return {"message": "pong"}


@app.get("/health", tags=["Test"])
def health():
    """Health endpoint for uptime checks."""
    return {"status": "ok"}
    
@app.get("/", tags=["Root"])
def root():
    """Welcome message for the root endpoint."""
    return {
        "message": "Welcome to the AI Developer Assistant API!",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
