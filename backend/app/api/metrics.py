"""
GET /metrics — Expose AI provider retry metrics for monitoring.
"""
from fastapi import APIRouter
from backend.app.services.ai_provider import retry_metrics

router = APIRouter()

@router.get("/metrics", tags=["Monitoring"])
def get_metrics():
    """
    Returns retry and backoff counters for AI provider calls.

    Fields:
    - total_requests: Total call_llm() invocations
    - total_successes: Successful responses returned
    - total_failures: Final failures after retries exhausted
    - total_retries: Total retry attempts
    - retries_exhausted: Requests that hit max retries
    - backoff_events: Number of backoff sleeps triggered
    - avg_success_latency_ms: Average latency for successful calls
    - by_provider: Per-provider breakdown of all counters
    """
    return retry_metrics.snapshot()