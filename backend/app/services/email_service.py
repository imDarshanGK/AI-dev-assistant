"""Weekly digest email — SMTP sending and HTML template."""

from __future__ import annotations
import secrets
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import smtplib
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from ..config import settings
from ..models import QueryHistory, User

# ── Helpers ──────────────────────────────────────────────────────────────────


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _build_unsubscribe_url(email: str, token: str) -> str:
    """Build the one-click unsubscribe URL for digest emails."""
    base = settings.digest_base_url.rstrip("/")
    query = urlencode({"email": email, "token": token})
    return f"{base}/subscribe/unsubscribe?{query}"


def _parse_score(result_json: str) -> int | None:
    """Extract overall_score from an analysis result JSON."""
    try:
        data = json.loads(result_json)
        return data.get("suggestions", {}).get("overall_score")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None


def _most_common_bug(issues: list[dict]) -> str | None:
    """Return the most frequent bug type from a list of debug issues."""
    from collections import Counter

    types = [i.get("type", "Unknown") for i in issues if i.get("type")]
    if not types:
        return None
    return Counter(types).most_common(1)[0][0]


# ── Stats computation ─────────────────────────────────────────────────────────


def compute_subscriber_stats(db: Session, email: str) -> dict | None:
    """Compute weekly analysis stats for a subscriber.

    Returns a dict ready for the email template, or None if the user
    has no analysis history.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None

    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # This week
    this_week: list[QueryHistory] = (
        db.query(QueryHistory)
        .filter(
            QueryHistory.user_id == user.id,
            QueryHistory.created_at >= week_ago,
        )
        .all()
    )

    if not this_week:
        return None

    # Last week (for week-over-week comparison)
    last_week: list[QueryHistory] = (
        db.query(QueryHistory)
        .filter(
            QueryHistory.user_id == user.id,
            QueryHistory.created_at >= two_weeks_ago,
            QueryHistory.created_at < week_ago,
        )
        .all()
    )

    total = len(this_week)
    languages: set[str] = set()
    scores: list[int] = []
    all_issues: list[dict] = []

    for h in this_week:
        try:
            data = json.loads(h.result_json)
        except json.JSONDecodeError:
            continue

        # Language from explanation
        lang = data.get("explanation", {}).get("language") or data.get("language")
        if lang:
            languages.add(lang)

        # Score from suggestions
        score = data.get("suggestions", {}).get("overall_score")
        if score is not None:
            scores.append(int(score))

        # Issues from debugging
        issues = data.get("debugging", {}).get("issues", [])
        all_issues.extend(issues)

    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    # Last week average for comparison
    last_scores: list[int] = []
    for h in last_week:
        s = _parse_score(h.result_json)
        if s is not None:
            last_scores.append(s)
    prev_avg = round(sum(last_scores) / len(last_scores), 1) if last_scores else None

    improvement: float | None = None
    trend: str = "stable"
    if avg_score is not None and prev_avg is not None and prev_avg > 0:
        improvement = round(((avg_score - prev_avg) / prev_avg) * 100, 1)
        if improvement > 2:
            trend = "up"
        elif improvement < -2:
            trend = "down"

    top_bug = _most_common_bug(all_issues)

    return {
        "email": email,
        "total_analyses": total,
        "languages": sorted(languages) if languages else ["Unknown"],
        "avg_score": avg_score,
        "prev_avg": prev_avg,
        "improvement": improvement,
        "trend": trend,
        "top_bug": top_bug,
        "total_issues": len(all_issues),
        "week_start": week_ago.strftime("%b %d"),
        "week_end": now.strftime("%b %d, %Y"),
    }


# ── Email template ────────────────────────────────────────────────────────────


def _build_html(stats: dict, unsubscribe_url: str) -> str:
    """Render the weekly digest HTML email."""
    score_line = ""
    if stats["avg_score"] is not None:
        emoji = {"up": "📈", "down": "📉", "stable": "➡️"}.get(stats["trend"], "➡️")
        arrow = {"up": "↑", "down": "↓", "stable": "→"}.get(stats["trend"], "→")
        change = ""
        if stats["improvement"] is not None:
            change = f" ({arrow} {abs(stats['improvement'])}% vs last week)"
        score_line = f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;"><strong>Average Score</strong></td>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;text-align:right;">{stats['avg_score']}/100 {emoji}{change}</td>
        </tr>"""

    bug_line = ""
    if stats["top_bug"]:
        bug_line = f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;"><strong>Most Common Bug</strong></td>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;text-align:right;">{stats['top_bug']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f1ec;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:32px 16px;">
  <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
    <tr><td style="background:#1a1a2e;padding:24px 32px;text-align:center;">
      <h1 style="margin:0;color:#f0a030;font-size:1.4rem;">QyverixAI Weekly Digest</h1>
      <p style="margin:4px 0 0;color:#aaa;font-size:0.85rem;">{stats['week_start']} – {stats['week_end']}</p>
    </td></tr>
    <tr><td style="padding:24px 32px;">
      <p style="margin:0 0 16px;color:#333;font-size:0.95rem;">Here&#39;s your weekly code analysis summary.</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e0dcd4;border-radius:6px;">
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;"><strong>Analyses Run</strong></td>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;text-align:right;">{stats['total_analyses']}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;"><strong>Languages</strong></td>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;text-align:right;">{', '.join(stats['languages'])}</td>
        </tr>
        {score_line}
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;"><strong>Issues Found</strong></td>
          <td style="padding:8px 12px;border-bottom:1px solid #e0dcd4;text-align:right;">{stats['total_issues']}</td>
        </tr>
        {bug_line}
      </table>
    </td></tr>
    <tr><td style="padding:0 32px 24px;text-align:center;">
      <a href="{stats.get('base_url', 'https://qyverixai.onrender.com')}/app" style="display:inline-block;padding:10px 24px;background:#f0a030;color:#1a1a2e;text-decoration:none;border-radius:6px;font-weight:bold;font-size:0.9rem;">Open QyverixAI</a>
    </td></tr>
    <tr><td style="padding:16px 32px;background:#faf8f5;font-size:0.75rem;color:#888;text-align:center;">
      <p style="margin:0;">This email was sent to {stats['email']} because you subscribed to the QyverixAI weekly digest.</p>
      <p style="margin:4px 0 0;"><a href="{unsubscribe_url}" style="color:#888;text-decoration:underline;">Unsubscribe</a></p>
    </td></tr>
  </table>
</td></tr></table>
</body>
</html>"""


def _build_text(stats: dict, unsubscribe_url: str) -> str:
    """Plain-text fallback for the digest email."""
    score = (
        f"Average Score: {stats['avg_score']}/100"
        if stats["avg_score"] is not None
        else ""
    )
    bug = f"Most Common Bug: {stats['top_bug']}" if stats["top_bug"] else ""
    return (
        f"QyverixAI Weekly Digest\n"
        f"{stats['week_start']} \u2013 {stats['week_end']}\n\n"
        f"Analyses Run: {stats['total_analyses']}\n"
        f"Languages: {', '.join(stats['languages'])}\n"
        f"{score}\n"
        f"Issues Found: {stats['total_issues']}\n"
        f"{bug}\n\n"
        f"Open QyverixAI: {stats.get('base_url', 'https://qyverixai.onrender.com')}/app\n\n"
        f"Unsubscribe: {unsubscribe_url}"
    )


# ── SMTP send ────────────────────────────────────────────────────────────────


def send_digest(stats: dict, unsubscribe_token: str) -> bool:
    """Build and send a weekly digest email via SMTP.

    Returns True on success, False on failure.
    """
    if not settings.digest_enabled or not settings.smtp_host:
        return False

    unsubscribe_url = _build_unsubscribe_url(stats["email"], unsubscribe_token)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"QyverixAI Weekly Digest — {stats['week_start']} to {stats['week_end']}"
    )
    msg["From"] = settings.email_from
    msg["To"] = stats["email"]

    msg.attach(MIMEText(_build_text(stats, unsubscribe_url), "plain"))
    msg.attach(MIMEText(_build_html(stats, unsubscribe_url), "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_port == 587:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(msg)
        return True
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "Failed to send digest to %s: %s", stats["email"], exc
        )
        return False
