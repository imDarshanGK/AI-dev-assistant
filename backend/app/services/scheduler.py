"""APScheduler integration — weekly Sunday digest dispatch."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import settings
from ..database import SessionLocal
from ..models import DigestSubscription
from ..observability import (
    DIGEST_EMAILS_FAILED_TOTAL,
    DIGEST_EMAILS_SENT_TOTAL,
    DIGEST_JOB_DURATION_SECONDS,
    DIGEST_JOBS_TOTAL,
    DIGEST_LAST_RUN_TIMESTAMP,
)
from .email_service import compute_subscriber_stats, send_digest

log = logging.getLogger(__name__)
scheduler = BackgroundScheduler(daemon=True)
JOB_ID = "weekly_digest"


def _send_weekly_digests() -> None:
    """Query all active subscribers and send them their weekly digest."""
    start = time.time()

    if not settings.digest_enabled:
        log.info("Digest disabled — skipping weekly run")
        DIGEST_JOBS_TOTAL.labels(result="skipped").inc()
        return

    db = SessionLocal()
    try:
        subs = (
            db.query(DigestSubscription)
            .filter(DigestSubscription.is_active.is_(True))
            .all()
        )
        if not subs:
            log.info("No active digest subscribers")
            DIGEST_JOBS_TOTAL.labels(result="no_subscribers").inc()
            return

        sent = 0
        for sub in subs:
            stats = compute_subscriber_stats(db, sub.email)
            if not stats:
                log.debug("No stats for %s, skipping", sub.email)
                continue
            ok = send_digest(stats, sub.unsubscribe_token)
            if ok:
                sub.last_sent_at = datetime.now(UTC)
                sent += 1
                DIGEST_EMAILS_SENT_TOTAL.inc()
            else:
                log.warning("Failed to deliver digest to %s", sub.email)
                DIGEST_EMAILS_FAILED_TOTAL.inc()

        db.commit()
        log.info("Weekly digest sent to %d/%d subscribers", sent, len(subs))
        DIGEST_JOBS_TOTAL.labels(result="success").inc()
    except Exception:
        log.exception("Error in weekly digest job")
        DIGEST_JOBS_TOTAL.labels(result="error").inc()
    finally:
        DIGEST_LAST_RUN_TIMESTAMP.set(time.time())
        DIGEST_JOB_DURATION_SECONDS.observe(time.time() - start)
        db.close()


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
