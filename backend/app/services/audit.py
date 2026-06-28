"""Audit logging for privileged admin actions.

Writes append-only :class:`~app.models.AuditLog` rows. Sensitive values in the
free-form ``details`` payload are redacted before they are persisted so the
trail never stores secrets, tokens, or password material.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog, User

# Substrings that mark a field as sensitive; matched case-insensitively against
# the key name. Matching values are replaced with ``REDACTED`` before storage.
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
)

REDACTED = "***REDACTED***"


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def redact(value: Any) -> Any:
    """Recursively replace sensitive values in dicts/lists with a placeholder."""
    if isinstance(value, dict):
        return {
            k: (REDACTED if _is_sensitive(str(k)) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def record_audit(
    db: Session,
    *,
    actor: User,
    action: str,
    target_type: str | None = None,
    target_id: str | int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Persist a single audit entry for ``actor`` and return it.

    ``details`` is redacted and serialised to JSON. The caller is responsible
    for committing the surrounding transaction.
    """
    safe_details = redact(details) if details else None
    entry = AuditLog(
        actor_id=actor.id,
        actor_email=actor.email,
        action=action,
        target_type=target_type,
        target_id=None if target_id is None else str(target_id),
        details=json.dumps(safe_details) if safe_details is not None else None,
        ip_address=ip_address,
    )
    db.add(entry)
    db.flush()
    return entry
