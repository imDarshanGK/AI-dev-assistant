"""APScheduler integration — weekly Sunday digest dispatch."""

from __future__ import annotations
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import settings
from ..database import SessionLocal
from ..models import DigestSubscription, AnalysisSchedule
from .email_service import compute_subscriber_stats, send_digest
from .ai_provider import run_analysis_pipeline

log = logging.getLogger(__name__)
scheduler = BackgroundScheduler(daemon=True)
DIGEST_JOB_ID = "weekly_digest"

# --- Analysis Scheduling ---



def start_scheduler() -> None:
    """Start the background scheduler with the weekly digest job."""
    if scheduler.get_job(JOB_ID):
        return

    log.info("Starting weekly digest scheduler (cron: 0 8 * * 0)")
    scheduler.add_job(
        _send_weekly_digests,
        trigger="cron",
        day_of_week="sun",
        hour=8,
        minute=0,
        id=JOB_ID,
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    """Shut down the background scheduler."""
    if scheduler.running:
        log.info("Stopping weekly digest scheduler")
        scheduler.shutdown(wait=False)
