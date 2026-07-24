"""Governance module: read-only audit trail access (Chapter 28)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import rbac
from app.core.database import get_db
from app.core.rbac import require_permission
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(tags=["governance"])


@router.get("/audit-logs")
def list_audit_logs(
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    _: User = Depends(require_permission(rbac.P_AUDIT_READ)),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    rows = q.order_by(AuditLog.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "actor_email": r.actor_email,
            "actor_role": r.actor_role,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "reason": r.reason,
            "correlation_id": r.correlation_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
