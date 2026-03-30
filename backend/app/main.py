from fastapi import FastAPI
from app.routers import explanation, debugging, suggestions

app = FastAPI(title="AI Developer Assistant", description="Beginner-friendly AI Developer Assistant API.")

# Include routers
app.include_router(explanation.router)
app.include_router(debugging.router)
app.include_router(suggestions.router)

@app.get("/ping", tags=["Test"])
def ping():
    """Sample test endpoint to check API status."""
    return {"message": "pong"}
