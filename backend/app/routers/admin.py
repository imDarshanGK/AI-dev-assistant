"""Admin router — privileged actions and the audit-log query API.

Every state-changing endpoint here is gated behind :func:`require_admin` and
records an append-only entry via :func:`record_audit`, giving a tamper-evident
trail of who did what and when.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, User
from ..schemas import AuditLogRecord, MessageResponse, RoleUpdateRequest
from ..security import require_admin
from ..services.audit import record_audit

router = APIRouter(prefix="/admin", tags=["Admin"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_record(entry: AuditLog) -> AuditLogRecord:
    return AuditLogRecord(
        id=entry.id,
        actor_id=entry.actor_id,
        actor_email=entry.actor_email,
        action=entry.action,
        target_type=entry.target_type,
        target_id=entry.target_id,
        details=json.loads(entry.details) if entry.details else None,
        ip_address=entry.ip_address,
        created_at=entry.created_at.isoformat(),
    )


@router.get("/audit-logs", response_model=list[AuditLogRecord])
def list_audit_logs(
    action: str | None = Query(None, description="Filter by exact action name."),
    actor_id: int | None = Query(None, description="Filter by acting admin's id."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return audit entries, newest first. Admin only."""
    query = select(AuditLog).order_by(AuditLog.id.desc())
    if action is not None:
        query = query.where(AuditLog.action == action)
    if actor_id is not None:
        query = query.where(AuditLog.actor_id == actor_id)

    entries = db.execute(query.limit(limit).offset(offset)).scalars().all()
    return [_to_record(entry) for entry in entries]


@router.put("/users/{user_id}/role", response_model=MessageResponse)
def update_user_role(
    user_id: int,
    payload: RoleUpdateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Grant or revoke a user's admin role, recording the change in the audit log."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    previous = user.is_admin
    user.is_admin = payload.is_admin
    record_audit(
        db,
        actor=admin,
        action="user.role_update",
        target_type="user",
        target_id=user.id,
        details={"from": previous, "to": payload.is_admin, "email": user.email},
        ip_address=_client_ip(request),
    )
    db.commit()
    return MessageResponse(
        message=f"User {user_id} admin role set to {payload.is_admin}."
    )


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a user account, recording the action in the audit log."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot delete their own account",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    email = user.email
    db.delete(user)
    record_audit(
        db,
        actor=admin,
        action="user.delete",
        target_type="user",
        target_id=user_id,
        details={"email": email},
        ip_address=_client_ip(request),
    )
    db.commit()
    return MessageResponse(message=f"User {user_id} deleted.")
