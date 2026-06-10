"""Compliance reporting router.

Exposes an authenticated workflow for generating compliance reports and
exporting them as PDF, CSV or JSON, plus read access to the audit trail. Every
endpoint is scoped to the authenticated user — a report only ever covers the
caller's own analysis history — and every report generation is recorded as an
audit event.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import AuditLogRecord, ReportRequest
from ..security import get_current_user
from ..services import audit
from ..services.report_builder import build_report
from ..services.report_exporters import export_report

router = APIRouter(prefix="/reports", tags=["Compliance Reports"])


def _audit_detail(report: dict, *, fmt: str | None = None) -> dict:
    detail = {
        "filters": report["metadata"]["filters"],
        "record_count": report["metadata"]["record_count"],
    }
    if fmt is not None:
        detail["format"] = fmt
    return detail


@router.post("/preview")
def preview_report(
    payload: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Build and return the structured report model without downloading a file.

    Intended for the UI to render filter results before the user commits to an
    export format.
    """
    report = build_report(db, current_user, payload.filters)
    audit.record_event(
        db,
        user_id=current_user.id,
        action="report.preview",
        resource=report["metadata"]["report_id"],
        detail=_audit_detail(report),
    )
    return report


@router.post("/generate")
def generate_report(
    payload: ReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Generate a compliance report and return it as a downloadable file."""
    report = build_report(db, current_user, payload.filters)
    content, media_type, extension = export_report(report, payload.format)

    audit.record_event(
        db,
        user_id=current_user.id,
        action="report.generate",
        resource=report["metadata"]["report_id"],
        detail=_audit_detail(report, fmt=payload.format),
    )

    filename = f"compliance-report-{report['metadata']['report_id']}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Id": report["metadata"]["report_id"],
        },
    )


@router.get("/audit", response_model=list[AuditLogRecord])
def list_audit_trail(
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuditLogRecord]:
    """Return the authenticated user's audit trail, newest first."""
    events = audit.list_events(db, current_user.id, limit=limit)
    return [
        AuditLogRecord(
            id=event.id,
            action=event.action,
            resource=event.resource,
            detail=json.loads(event.detail_json or "{}"),
            created_at=event.created_at.isoformat(),
        )
        for event in events
    ]
