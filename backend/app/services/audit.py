"""Audit-trail service — append-only recording of compliance-relevant events.

Centralising writes here keeps the serialisation of the ``detail`` payload and
the commit semantics in one place, so routers only have to describe *what*
happened, not how it is persisted.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog


def record_event(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    resource: str = "",
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    """Append one event to the audit trail and return the persisted row."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        detail_json=json.dumps(detail or {}, default=str),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_events(db: Session, user_id: int, limit: int = 100) -> list[AuditLog]:
    """Return the most recent audit events for ``user_id``, newest first."""
    return list(
        db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
