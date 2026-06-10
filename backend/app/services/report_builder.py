"""Format-agnostic compliance report builder.

This module turns a user's stored analysis history into a single, structured
report model — a plain ``dict`` — enriched with compliance metadata (report id,
generation timestamp, applied filters, source/version information) and summary
statistics. The model is deliberately format-neutral: the exporters in
``report_exporters`` render it to PDF, CSV or JSON without any of them needing
to know how the data was gathered or filtered.

Keeping the builder separate from the exporters means a new export format can be
added by writing one renderer, with zero changes to the reporting logic.
"""

from __future__ import annotations

import json
import os
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import QueryHistory, User
from ..schemas import ReportFilters

# Pinned alongside the FastAPI app version so a report records which build of the
# analysis engine produced the underlying data.
ANALYSIS_VERSION = "3.0.0"

_VALID_SEVERITIES = ("error", "warning", "info")


def _parse_result(result_json: str) -> dict[str, Any]:
    """Best-effort decode of a stored ``result_json`` blob into a dict."""
    try:
        parsed = json.loads(result_json)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_language(result: dict[str, Any]) -> str:
    explanation = result.get("explanation")
    if isinstance(explanation, dict) and explanation.get("language"):
        return str(explanation["language"]).lower()
    if result.get("language"):
        return str(result["language"]).lower()
    return "unknown"


def _extract_score(result: dict[str, Any]) -> int | None:
    suggestions = result.get("suggestions")
    if isinstance(suggestions, dict) and isinstance(
        suggestions.get("overall_score"), int
    ):
        return suggestions["overall_score"]
    if isinstance(result.get("overall_score"), int):
        return result["overall_score"]
    if isinstance(result.get("score"), int):
        return result["score"]
    return None


def _extract_severity_counts(result: dict[str, Any]) -> Counter:
    """Count issues per severity from a stored analysis result."""
    counts: Counter = Counter()
    debugging = result.get("debugging")
    issues = debugging.get("issues") if isinstance(debugging, dict) else None
    if not isinstance(issues, list):
        issues = result.get("issues") if isinstance(result.get("issues"), list) else []
    for issue in issues:
        if isinstance(issue, dict):
            severity = str(issue.get("severity", "")).lower()
            if severity in _VALID_SEVERITIES:
                counts[severity] += 1
    return counts


def _normalise_record(entry: QueryHistory) -> dict[str, Any]:
    """Project a QueryHistory row into a flat, report-friendly record."""
    result = _parse_result(entry.result_json)
    severity_counts = _extract_severity_counts(result)
    created_at = entry.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return {
        "id": entry.id,
        "action": entry.action,
        "language": _extract_language(result),
        "score": _extract_score(result),
        "issue_count": int(sum(severity_counts.values())),
        "severity_counts": {sev: severity_counts.get(sev, 0) for sev in _VALID_SEVERITIES},
        "created_at": created_at.astimezone(UTC).isoformat(),
        "code_preview": (entry.code or "").strip()[:120].replace("\n", " "),
    }


def _matches(record: dict[str, Any], filters: ReportFilters) -> bool:
    """Apply the post-projection filters (language / severity / score) to a record."""
    if filters.actions and record["action"].lower() not in filters.actions:
        return False
    if filters.languages and record["language"] not in filters.languages:
        return False
    if filters.severities:
        if not any(record["severity_counts"].get(sev, 0) > 0 for sev in filters.severities):
            return False
    score = record["score"]
    if filters.min_score is not None and (score is None or score < filters.min_score):
        return False
    if filters.max_score is not None and (score is None or score > filters.max_score):
        return False
    if filters.search:
        needle = filters.search.lower()
        if needle not in record["code_preview"].lower():
            return False
    return True


def build_report(db: Session, user: User, filters: ReportFilters) -> dict[str, Any]:
    """Build a structured compliance report for ``user`` honouring ``filters``.

    The returned dict has three top-level sections:

    * ``metadata`` — report id, generation timestamp, requesting user, applied
      filters, and analysis source/version information.
    * ``summary`` — aggregate statistics over the included records.
    * ``records`` — the per-analysis rows that make up the report body.
    """
    stmt = select(QueryHistory).where(QueryHistory.user_id == user.id)
    # Date-range selection is pushed to SQL where it is cheap and indexed.
    if filters.start_date is not None:
        start = filters.start_date
        stmt = stmt.where(QueryHistory.created_at >= start.replace(tzinfo=None))
    if filters.end_date is not None:
        end = filters.end_date
        stmt = stmt.where(QueryHistory.created_at <= end.replace(tzinfo=None))
    stmt = stmt.order_by(QueryHistory.created_at.asc())

    rows = db.execute(stmt).scalars().all()

    records: list[dict[str, Any]] = []
    for entry in rows:
        record = _normalise_record(entry)
        if _matches(record, filters):
            records.append(record)

    summary = _summarise(records)
    generated_at = datetime.now(UTC)

    return {
        "metadata": {
            "report_id": str(uuid.uuid4()),
            "generated_at": generated_at.isoformat(),
            "generated_by": {"user_id": user.id, "email": user.email},
            "analysis_version": ANALYSIS_VERSION,
            "source": "QyverixAI",
            "ai_provider": os.getenv("AI_PROVIDER", "rule-based"),
            "filters": _describe_filters(filters),
            "record_count": len(records),
        },
        "summary": summary,
        "records": records,
    }


def _summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_action: Counter = Counter()
    by_language: Counter = Counter()
    severity_totals: Counter = Counter()
    scores: list[int] = []

    for record in records:
        by_action[record["action"]] += 1
        by_language[record["language"]] += 1
        for sev in _VALID_SEVERITIES:
            severity_totals[sev] += record["severity_counts"].get(sev, 0)
        if record["score"] is not None:
            scores.append(record["score"])

    total_issues = int(sum(severity_totals.values()))
    average_score = round(sum(scores) / len(scores), 1) if scores else None

    return {
        "total_records": len(records),
        "total_issues": total_issues,
        "by_action": dict(by_action),
        "by_language": dict(by_language),
        "by_severity": {sev: severity_totals.get(sev, 0) for sev in _VALID_SEVERITIES},
        "average_score": average_score,
        "scored_records": len(scores),
    }


def _describe_filters(filters: ReportFilters) -> dict[str, Any]:
    """Serialise the applied filters for the report metadata (JSON-safe)."""
    return {
        "start_date": filters.start_date.isoformat() if filters.start_date else None,
        "end_date": filters.end_date.isoformat() if filters.end_date else None,
        "actions": filters.actions,
        "languages": filters.languages,
        "severities": filters.severities,
        "min_score": filters.min_score,
        "max_score": filters.max_score,
        "search": filters.search,
    }
