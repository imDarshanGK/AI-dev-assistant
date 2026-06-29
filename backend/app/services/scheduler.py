"""APScheduler integration — weekly Sunday digest dispatch."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
scheduler = BackgroundScheduler(daemon=True)
DIGEST_JOB_ID = "weekly_digest"


def _send_weekly_digests() -> None:
    """Send weekly digest emails to all active subscribers."""
    log.info("Sending weekly digests")
    from ..database import SessionLocal
    from ..models import DigestSubscription
    from .email_service import compute_subscriber_stats, send_digest

    db = SessionLocal()
    try:
        subscribers = (
            db.query(DigestSubscription)
            .filter(DigestSubscription.is_active.is_(True))
            .all()
        )
        stats = compute_subscriber_stats(db)
        for sub in subscribers:
            send_digest(sub.email, sub.unsubscribe_token, stats)
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the background scheduler with the weekly digest job."""
    if scheduler.get_job(DIGEST_JOB_ID):
        return

    log.info("Starting weekly digest scheduler (cron: 0 8 * * 0)")
    scheduler.add_job(
        _send_weekly_digests,
        trigger="cron",
        day_of_week="sun",
        hour=8,
        minute=0,
        id=DIGEST_JOB_ID,
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    """Shut down the background scheduler."""
    if scheduler.running:
        log.info("Stopping weekly digest scheduler")
        scheduler.shutdown(wait=False)
