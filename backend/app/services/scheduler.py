"""APScheduler integration — weekly Sunday digest dispatch."""

from __future__ import annotations
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import settings
from ..database import SessionLocal
from ..models import DigestSubscription, AnalysisSchedule
from .email_service import compute_subscriber_stats, send_digest
from .ai_provider import run_analysis_pipeline # Assuming this exists to run the analysis

log = logging.getLogger(__name__)
scheduler = BackgroundScheduler(daemon=True)
DIGEST_JOB_ID = "weekly_digest"

# --- Analysis Scheduling ---

def _run_scheduled_analysis(schedule_id: int) -> None:
    """Execute a scheduled analysis job."""
    db = SessionLocal()
    try:
        schedule = db.query(AnalysisSchedule).get(schedule_id)
        if not schedule or not schedule.is_active:
            return

        log.info("Running scheduled analysis for %s (type: %s)", schedule.target_repo, schedule.analysis_type)
        
        # This is a hypothetical call based on the project structure.
        # It needs to trigger the actual analysis logic.
        result = run_analysis_pipeline(
            db, 
            schedule.user_id, 
            schedule.target_repo, 
            schedule.analysis_type
        )
        
        schedule.last_run_at = datetime.now(UTC)
        db.commit()
        log.info("Scheduled analysis %d completed", schedule_id)
    except Exception:
        log.exception("Error in scheduled analysis job %d", schedule_id)
    finally:
        db.close()


def add_analysis_schedule(schedule_id: int, cron_expr: str) -> None:
    """Add or update a scheduled analysis job in the scheduler."""
    # Split cron expression into parts: minute, hour, day, month, day_of_week
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError("Invalid cron expression")

    scheduler.add_job(
        _run_scheduled_analysis,
        trigger="cron",
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
        args=[schedule_id],
        id=f"analysis_{schedule_id}",
        replace_existing=True,
    )
    log.info("Added analysis schedule %d with cron '%s'", schedule_id, cron_expr)


def remove_analysis_schedule(schedule_id: int) -> None:
    """Remove a scheduled analysis job."""
    job_id = f"analysis_{schedule_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        log.info("Removed analysis schedule %d", schedule_id)


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
            else:
                log.warning("Failed to deliver digest to %s", sub.email)

        db.commit()
        log.info("Weekly digest sent to %d/%d subscribers", sent, len(subs))
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
