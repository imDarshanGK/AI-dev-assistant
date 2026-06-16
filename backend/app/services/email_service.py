"""Transactional and digest email — Jinja2 templates, premailer inlining, SMTP."""

from __future__ import annotations

import json
import logging
import secrets
import smtplib
from collections import Counter
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urlencode

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from premailer import transform as inline_css
from sqlalchemy.orm import Session

from ..config import settings
from ..models import QueryHistory, User

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"

EMAIL_TEMPLATES = frozenset({"welcome", "reset", "notification", "digest"})

# Common preview URL typos → canonical template name
TEMPLATE_ALIASES: dict[str, str] = {
    "welcom": "welcome",
    "welcone": "welcome",
    "notifications": "notification",
    "notify": "notification",
    "password-reset": "reset",
    "password_reset": "reset",
    "digest-weekly": "digest",
    "weekly": "digest",
}

SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"

_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _app_url() -> str:
    return f"{settings.digest_base_url.rstrip('/')}/app"


def _footer_urls() -> dict[str, str]:
    base = settings.digest_base_url.rstrip("/")
    return {
        "privacy_url": f"{base}/app#privacy",
        "terms_url": f"{base}/app#terms",
        "preferences_url": f"{base}/app#notifications",
    }


def _base_email_context(**extra: object) -> dict:
    return {**_footer_urls(), **extra}


def _build_unsubscribe_url(email: str, token: str) -> str:
    """Build the one-click unsubscribe URL for digest emails."""
    base = settings.digest_base_url.rstrip("/")
    query = urlencode({"email": email, "token": token})
    return f"{base}/subscribe/unsubscribe?{query}"


def _feedback_urls(email: str, digest_id: str | None = None) -> dict[str, str]:
    base = settings.digest_base_url.rstrip("/")
    token = digest_id or "preview"
    query = urlencode({"email": email, "token": token})
    return {
        "feedback_up_url": f"{base}/subscribe/feedback?{query}&rating=up",
        "feedback_down_url": f"{base}/subscribe/feedback?{query}&rating=down",
    }


def _parse_score(result_json: str) -> int | None:
    """Extract overall_score from an analysis result JSON."""
    try:
        data = json.loads(result_json)
        return data.get("suggestions", {}).get("overall_score")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None


def _most_common_bug(issues: list[dict]) -> str | None:
    """Return the most frequent bug type from a list of debug issues."""
    types = [i.get("type", "Unknown") for i in issues if i.get("type")]
    if not types:
        return None
    return Counter(types).most_common(1)[0][0]


def _trend_arrow(trend: str) -> str:
    return {"up": "↑", "down": "↓", "stable": "→"}.get(trend, "→")


def score_sparkline(scores: list[float | int | None]) -> str:
    """Build an email-safe text sparkline from weekly scores."""
    valid = [float(s) for s in scores if s is not None]
    if not valid:
        return "▁▁▁▁"

    low, high = min(valid), max(valid)
    if high == low:
        mid = SPARKLINE_CHARS[len(SPARKLINE_CHARS) // 2]
        return mid * len(scores)

    chars: list[str] = []
    for score in scores:
        if score is None:
            chars.append(SPARKLINE_CHARS[0])
            continue
        ratio = (float(score) - low) / (high - low)
        idx = min(int(ratio * (len(SPARKLINE_CHARS) - 1)), len(SPARKLINE_CHARS) - 1)
        chars.append(SPARKLINE_CHARS[idx])
    return "".join(chars)


def _weekly_average_scores(
    db: Session,
    user_id: int,
    *,
    now: datetime,
    weeks: int = 4,
) -> list[dict]:
    """Return average scores for the last N weeks (oldest first)."""
    results: list[dict] = []
    for offset in range(weeks - 1, -1, -1):
        week_end = now - timedelta(days=7 * offset)
        week_start = week_end - timedelta(days=7)
        rows: list[QueryHistory] = (
            db.query(QueryHistory)
            .filter(
                QueryHistory.user_id == user_id,
                QueryHistory.created_at >= week_start,
                QueryHistory.created_at < week_end,
            )
            .all()
        )
        scores: list[int] = []
        for row in rows:
            score = _parse_score(row.result_json)
            if score is not None:
                scores.append(score)
        avg = round(sum(scores) / len(scores), 1) if scores else None
        label = week_start.strftime("%b %d")
        results.append({"label": label, "score": avg})
    return results


def _score_streak_weeks(weekly_scores: list[dict]) -> int:
    """Count consecutive weeks (from most recent) with improving scores."""
    scores = [w["score"] for w in weekly_scores if w.get("score") is not None]
    if len(scores) < 2:
        return 0

    streak = 0
    for idx in range(len(scores) - 1, 0, -1):
        if scores[idx] > scores[idx - 1]:
            streak += 1
        else:
            break
    return streak


def _focus_recommendations(
    *,
    avg_score: float | None,
    top_bug: str | None,
    total_issues: int,
    languages: list[str],
) -> list[str]:
    """Generate actionable focus items for the next digest cycle."""
    items: list[str] = []
    if top_bug:
        items.append(f"Prioritize fixing recurring {top_bug} patterns.")
    if avg_score is not None and avg_score < 70:
        items.append(
            "Add docstrings and inline comments to lift your documentation score."
        )
    if total_issues > 10:
        items.append(
            "Tackle high-severity issues first — sort by error before warnings."
        )
    if len(languages) > 2:
        items.append(
            f"Standardize patterns across {', '.join(languages[:3])} for consistency."
        )
    if not items:
        items.append(
            "Keep running analyses weekly to maintain momentum and track trends."
        )
    return items[:3]


# ── Template rendering ─────────────────────────────────────────────────────────


def resolve_template_name(name: str) -> str | None:
    """Resolve a preview path segment to a canonical template name."""
    key = name.strip().lower()
    if key in EMAIL_TEMPLATES:
        return key
    return TEMPLATE_ALIASES.get(key)


def render_template(name: str, context: dict, *, inline_styles: bool = True) -> str:
    """Render an email template by name with the given context."""
    if name not in EMAIL_TEMPLATES:
        raise TemplateNotFound(name)

    merged = _base_email_context(**context)
    template = _jinja_env.get_template(f"{name}.html")
    html = template.render(**merged)

    if inline_styles:
        html = inline_css(
            html,
            keep_style_tags=False,
            strip_important=False,
            disable_validation=True,
        )

    return html


def preview_context(template: str) -> dict:
    """Sample context for local email preview in development."""
    base = settings.digest_base_url.rstrip("/")
    sample_email = "developer@example.com"
    weekly_scores = [
        {"label": "May 11", "score": 62.0},
        {"label": "May 18", "score": 68.0},
        {"label": "May 25", "score": 74.0},
        {"label": "Jun 01", "score": 78.5},
    ]
    sparkline = score_sparkline([w["score"] for w in weekly_scores])

    contexts: dict[str, dict] = {
        "welcome": {
            "preheader": "Your QyverixAI account is ready — analyze your first file in seconds.",
            "recipient_name": "Alex",
            "email": sample_email,
            "app_url": f"{base}/app",
            "unsubscribe_url": None,
        },
        "reset": {
            "preheader": "Reset your QyverixAI password — link expires in 30 minutes.",
            "email": sample_email,
            "reset_url": f"{base}/app?reset=preview-token",
            "expires_minutes": 30,
            "request_timestamp": "Jun 08, 2026 at 2:34 PM UTC",
            "request_ip": "203.0.113.42",
            "request_location": "Bengaluru, India",
            "security_url": f"{base}/app#security",
            "unsubscribe_url": None,
        },
        "notification": {
            "preheader": "Analysis complete — quality score 84/100 with 3 issues found.",
            "email": sample_email,
            "title": "Analysis complete",
            "message": (
                "Your code analysis finished successfully. "
                "Review the quality breakdown and prioritized fixes below."
            ),
            "quality_score": "84/100",
            "files_analyzed": 3,
            "top_issue": "BareExcept",
            "report_url": f"{base}/app",
            "report_label": "View Report",
            "issues_url": f"{base}/app#issues",
            "cta_url": f"{base}/app",
            "cta_label": "View Report",
            "unsubscribe_url": None,
        },
        "digest": {
            "preheader": "Your weekly digest: 14 analyses, avg score 78.5 — up 12% this week.",
            "email": sample_email,
            "week_start": "Jun 01",
            "week_end": "Jun 08, 2026",
            "total_analyses": 14,
            "languages": ["Python", "TypeScript"],
            "avg_score": 78.5,
            "improvement": 12.0,
            "trend": "up",
            "trend_arrow": "↑",
            "top_bug": "BareExcept",
            "total_issues": 23,
            "weekly_scores": weekly_scores,
            "score_sparkline": sparkline,
            "score_streak_weeks": 3,
            "focus_recommendations": _focus_recommendations(
                avg_score=78.5,
                top_bug="BareExcept",
                total_issues=23,
                languages=["Python", "TypeScript"],
            ),
            "app_url": f"{base}/app",
            "unsubscribe_url": (
                f"{base}/subscribe/unsubscribe?"
                "email=developer%40example.com&token=preview"
            ),
            **_feedback_urls(sample_email),
        },
    }
    return contexts[template]


# ── Stats computation ─────────────────────────────────────────────────────────


def compute_subscriber_stats(db: Session, email: str) -> dict | None:
    """Compute weekly analysis stats for a subscriber."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None

    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

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

        lang = data.get("explanation", {}).get("language") or data.get("language")
        if lang:
            languages.add(lang)

        score = data.get("suggestions", {}).get("overall_score")
        if score is not None:
            scores.append(int(score))

        issues = data.get("debugging", {}).get("issues", [])
        all_issues.extend(issues)

    avg_score = round(sum(scores) / len(scores), 1) if scores else None

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
    lang_list = sorted(languages) if languages else ["Unknown"]
    weekly_scores = _weekly_average_scores(db, user.id, now=now, weeks=4)
    streak = _score_streak_weeks(weekly_scores)

    return {
        "email": email,
        "total_analyses": total,
        "languages": lang_list,
        "avg_score": avg_score,
        "prev_avg": prev_avg,
        "improvement": improvement,
        "trend": trend,
        "trend_arrow": _trend_arrow(trend),
        "top_bug": top_bug,
        "total_issues": len(all_issues),
        "week_start": week_ago.strftime("%b %d"),
        "week_end": now.strftime("%b %d, %Y"),
        "app_url": _app_url(),
        "weekly_scores": weekly_scores,
        "score_sparkline": score_sparkline([w["score"] for w in weekly_scores]),
        "score_streak_weeks": streak,
        "focus_recommendations": _focus_recommendations(
            avg_score=avg_score,
            top_bug=top_bug,
            total_issues=len(all_issues),
            languages=lang_list,
        ),
    }


def _digest_template_context(stats: dict, unsubscribe_url: str) -> dict:
    feedback = _feedback_urls(stats["email"])
    return {
        **_base_email_context(),
        **stats,
        **feedback,
        "preheader": (
            f"Your weekly digest: {stats['total_analyses']} analyses"
            + (
                f", avg score {stats['avg_score']}"
                if stats.get("avg_score") is not None
                else ""
            )
            + ".",
        ),
        "unsubscribe_url": unsubscribe_url,
    }


def _build_digest_text(stats: dict, unsubscribe_url: str) -> str:
    """Plain-text fallback for the digest email."""
    score = (
        f"Average Score: {stats['avg_score']}/100"
        if stats["avg_score"] is not None
        else ""
    )
    bug = f"Most Common Bug: {stats['top_bug']}" if stats.get("top_bug") else ""
    focus = ""
    if stats.get("focus_recommendations"):
        focus = "\nFocus for next week:\n" + "\n".join(
            f"- {item}" for item in stats["focus_recommendations"]
        )
    return (
        f"QyverixAI Weekly Digest\n"
        f"{stats['week_start']} \u2013 {stats['week_end']}\n\n"
        f"Analyses Run: {stats['total_analyses']}\n"
        f"Languages: {', '.join(stats['languages'])}\n"
        f"{score}\n"
        f"Issues Found: {stats['total_issues']}\n"
        f"{bug}\n"
        f"{focus}\n\n"
        f"Open QyverixAI: {stats.get('app_url', _app_url())}\n\n"
        f"Unsubscribe: {unsubscribe_url}"
    )


def _build_welcome_text(*, app_url: str) -> str:
    return (
        "Welcome to QyverixAI\n\n"
        "Your account is ready. Paste any code and get instant bug detection, "
        "plain-English explanations, and a quality score — no setup needed.\n\n"
        "Get started:\n"
        "1. Paste Code\n"
        "2. Run Analysis\n"
        "3. Fix Issues\n\n"
        f"Analyze your first file: {app_url}"
    )


def _build_reset_text(
    *,
    reset_url: str,
    expires_minutes: int,
    request_timestamp: str | None = None,
    request_ip: str | None = None,
) -> str:
    security = ""
    if request_timestamp or request_ip:
        security = "\nSecurity context:\n"
        if request_timestamp:
            security += f"Time: {request_timestamp}\n"
        if request_ip:
            security += f"IP: {request_ip}\n"
    return (
        "Reset your QyverixAI password\n\n"
        f"Use this link to choose a new password (expires in {expires_minutes} minutes):\n"
        f"{reset_url}\n"
        f"{security}\n"
        "If you did not request this, you can safely ignore this email."
    )


def _build_notification_text(
    *,
    title: str,
    message: str,
    report_url: str | None,
    issues_url: str | None,
) -> str:
    lines = [title, "", message]
    if report_url:
        lines.extend(["", f"View Report: {report_url}"])
    if issues_url:
        lines.append(f"See All Issues: {issues_url}")
    return "\n".join(lines)


# ── SMTP send ────────────────────────────────────────────────────────────────


def _send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    """Send a multipart email via SMTP. Returns True on success."""
    if not settings.smtp_host:
        logger.debug("SMTP not configured; skipping email to %s", to)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_port == 587:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(msg)
        return True
    except Exception as exc:
        logger.warning("Failed to send email to %s: %s", to, exc)
        return False


def send_welcome_email(email: str, *, recipient_name: str | None = None) -> bool:
    """Send the branded welcome email after signup."""
    context = {
        "preheader": "Your QyverixAI account is ready — analyze your first file in seconds.",
        "email": email,
        "recipient_name": recipient_name,
        "app_url": _app_url(),
        "unsubscribe_url": None,
    }
    html = render_template("welcome", context)
    text = _build_welcome_text(app_url=context["app_url"])
    return _send_email(email, "Welcome to QyverixAI", html, text)


def send_password_reset_email(
    email: str,
    reset_url: str,
    *,
    expires_minutes: int = 30,
    request_timestamp: str | None = None,
    request_ip: str | None = None,
    request_location: str | None = None,
) -> bool:
    """Send a branded password-reset email with expiry notice."""
    base = settings.digest_base_url.rstrip("/")
    context = {
        "preheader": f"Reset your QyverixAI password — link expires in {expires_minutes} minutes.",
        "email": email,
        "reset_url": reset_url,
        "expires_minutes": expires_minutes,
        "request_timestamp": request_timestamp,
        "request_ip": request_ip,
        "request_location": request_location,
        "security_url": f"{base}/app#security",
        "unsubscribe_url": None,
    }
    html = render_template("reset", context)
    text = _build_reset_text(
        reset_url=reset_url,
        expires_minutes=expires_minutes,
        request_timestamp=request_timestamp,
        request_ip=request_ip,
    )
    return _send_email(email, "Reset your QyverixAI password", html, text)


def send_notification_email(
    email: str,
    title: str,
    message: str,
    *,
    cta_url: str | None = None,
    cta_label: str | None = None,
    quality_score: str | int | None = None,
    files_analyzed: int | None = None,
    top_issue: str | None = None,
    report_url: str | None = None,
    report_label: str | None = None,
    issues_url: str | None = None,
) -> bool:
    """Send a branded notification for analysis complete or system events."""
    report_link = report_url or cta_url
    report_text = report_label or cta_label or "View Report"
    context = {
        "preheader": message[:120] if message else title,
        "email": email,
        "title": title,
        "message": message,
        "cta_url": cta_url,
        "cta_label": cta_label,
        "quality_score": quality_score,
        "files_analyzed": files_analyzed,
        "top_issue": top_issue,
        "report_url": report_link,
        "report_label": report_text,
        "issues_url": issues_url,
        "unsubscribe_url": None,
    }
    html = render_template("notification", context)
    text = _build_notification_text(
        title=title,
        message=message,
        report_url=report_link,
        issues_url=issues_url,
    )
    return _send_email(email, f"{title} — QyverixAI", html, text)


def send_digest(stats: dict, unsubscribe_token: str) -> bool:
    """Build and send a weekly digest email via SMTP."""
    if not settings.digest_enabled or not settings.smtp_host:
        return False

    unsubscribe_url = _build_unsubscribe_url(stats["email"], unsubscribe_token)
    template_context = _digest_template_context(stats, unsubscribe_url)
    html = render_template("digest", template_context)
    text = _build_digest_text(stats, unsubscribe_url)

    subject = f"QyverixAI Weekly Digest — {stats['week_start']} to {stats['week_end']}"
    return _send_email(stats["email"], subject, html, text)
