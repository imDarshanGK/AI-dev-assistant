"""
APScheduler integration — weekly Sunday digest dispatch.

Jobs are throttled via JobThrottle to prevent overwhelming the email
provider or database under subscriber volume spikes.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import settings
from ..database import SessionLocal
from ..models import DigestSubscription
from .email_service import compute_subscriber_stats, send_digest
from .job_throttle import ThrottleConfig, throttled_batch

log = logging.getLogger(__name__)
scheduler = BackgroundScheduler(daemon=True)
JOB_ID = "weekly_digest"

# ── Throttle config ────────────────────────────────────────────────────────────
# Tunable via environment variables so ops can adjust without code changes.

_THROTTLE_CONFIG = ThrottleConfig(
    max_concurrent_workers=int(os.getenv("DIGEST_MAX_WORKERS", "3")),
    max_queue_size=int(os.getenv("DIGEST_MAX_QUEUE", "50")),
    min_interval_seconds=float(os.getenv("DIGEST_MIN_INTERVAL_S", "0.5")),
    error_rate_threshold=float(os.getenv("DIGEST_ERROR_THRESHOLD", "0.3")),
    backoff_multiplier=float(os.getenv("DIGEST_BACKOFF_MULTIPLIER", "2.0")),
)


# ── Worker function ────────────────────────────────────────────────────────────

def _deliver_digest(sub_data: dict) -> bool:
    """
    Send a digest to one subscriber.

    Accepts a plain dict (not a SQLAlchemy model) so it is safe to call
    from a worker thread after the originating DB session is closed.

    Returns True on success, False on failure.
    """
    db = SessionLocal()
    try:
        stats = compute_subscriber_stats(db, sub_data["email"])
        if not stats:
            log.debug("No stats for %s, skipping", sub_data["email"])
            return False

        ok = send_digest(stats, sub_data["unsubscribe_token"])
        if ok:
            # Update last_sent_at in its own session to avoid cross-thread
            # SQLAlchemy session sharing.
            (
                db.query(DigestSubscription)
                .filter(DigestSubscription.id == sub_data["id"])
                .update({"last_sent_at": datetime.now(UTC)})
            )
            db.commit()
        else:
            log.warning("Failed to deliver digest to %s", sub_data["email"])
        return ok
    except Exception:
        log.exception("Error delivering digest to %s", sub_data.get("email"))
        db.rollback()
        return False
    finally:
        db.close()


# ── Main job ───────────────────────────────────────────────────────────────────

def _send_weekly_digests() -> None:
    """
    Query all active subscribers and dispatch their weekly digest.

    Uses throttled_batch() so concurrent workers and send rate are
    capped — preventing spikes that would overwhelm the email provider
    or database connection pool.
    """
    if not settings.digest_enabled:
        log.info("Digest disabled — skipping weekly run")
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
            return

        # Serialize to plain dicts before closing the session so worker
        # threads don't touch the SQLAlchemy session after it closes.
        sub_dicts = [
            {
                "id": s.id,
                "email": s.email,
                "unsubscribe_token": s.unsubscribe_token,
            }
            for s in subs
        ]
    except Exception:
        log.exception("Failed to query digest subscribers")
        return
    finally:
        db.close()

    log.info(
        "Starting throttled digest dispatch for %d subscribers "
        "(max_workers=%d, interval=%.2fs)",
        len(sub_dicts),
        _THROTTLE_CONFIG.max_concurrent_workers,
        _THROTTLE_CONFIG.min_interval_seconds,
    )

    result = throttled_batch(
        items=sub_dicts,
        worker_fn=_deliver_digest,
        config=_THROTTLE_CONFIG,
        job_label="digest",
    )

    log.info(
        "Weekly digest complete — sent=%d failed=%d skipped=%d total=%d error_rate=%.0f%%",
        result["sent"],
        result["failed"],
        result["skipped"],
        result["total"],
        result["error_rate"] * 100,
    )


# ── Scheduler lifecycle ────────────────────────────────────────────────────────

def start_scheduler() -> None:
    """Start the background scheduler with the weekly digest job."""
    if scheduler.get_job(JOB_ID):
        return

    log.info(
        "Starting weekly digest scheduler (cron: 0 8 * * 0) "
        "with throttle config: max_workers=%d interval=%.2fs",
        _THROTTLE_CONFIG.max_concurrent_workers,
        _THROTTLE_CONFIG.min_interval_seconds,
    )
    scheduler.add_job(
        _send_weekly_digests,
        trigger="cron",
        day_of_week="sun",
        hour=8,
        minute=0,
        id=JOB_ID,
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()


def stop_scheduler() -> None:
    """Shut down the background scheduler."""
    if scheduler.running:
        log.info("Stopping weekly digest scheduler")
        scheduler.shutdown(wait=False)