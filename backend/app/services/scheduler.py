"""APScheduler integration — weekly Sunday digest dispatch."""

from __future__ import annotations
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import settings
from ..database import SessionLocal
from ..models import DigestSubscription
from .email_service import compute_subscriber_stats, send_digest

log = logging.getLogger(__name__)
scheduler = BackgroundScheduler(daemon=True)
JOB_ID = "weekly_digest"


def _send_weekly_digests() -> None:
    """Query all active subscribers and send them their weekly digest."""
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

        # Snapshot subscriber primitives to avoid N+1 reload queries and holding ORM objects active
        subs_data = [
            {
                "id": sub.id,
                "email": sub.email,
                "unsubscribe_token": sub.unsubscribe_token,
            }
            for sub in subs
        ]
        # Rollback the read transaction immediately to release locks/connection
        db.rollback()

        sent = 0
        failed = 0
        for sub_info in subs_data:
            sub_id = sub_info["id"]
            email = sub_info["email"]
            token = sub_info["unsubscribe_token"]

            try:
                # 1. Fetch statistics inside a transaction
                stats = compute_subscriber_stats(db, email)
                
                # Always release the database transaction immediately after the read queries
                db.rollback()

                if not stats:
                    log.debug("No stats for %s, skipping", email)
                    continue

                # 2. Trigger the SMTP network call outside any open database transaction
                ok = send_digest(stats, token)

                if ok:
                    # 3. Update the specific subscriber's timestamp in a fresh, isolated transaction
                    sub_record = (
                        db.query(DigestSubscription)
                        .filter(DigestSubscription.id == sub_id)
                        .first()
                    )
                    if sub_record:
                        sub_record.last_sent_at = datetime.now(UTC)
                        db.commit()
                        sent += 1
                    else:
                        db.rollback()
                        log.warning("Subscriber record ID %d not found during update", sub_id)
                        failed += 1
                else:
                    log.warning("Failed to deliver digest to %s", email)
                    failed += 1
            except Exception:
                db.rollback()
                log.exception("Error processing digest for %s — skipping", email)
                failed += 1

        log.info(
            "Weekly digest run complete: %d sent, %d failed, %d total",
            sent,
            failed,
            len(subs_data),
        )
    except Exception:
        log.exception("Error in weekly digest job")
    finally:
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
