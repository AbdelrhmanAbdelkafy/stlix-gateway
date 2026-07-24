"""Append-only audit trail service (Chapter 28: Audit Trail).

Answers who / what / when / why / with-what-authority for every important
action. Records are only ever inserted — never updated or deleted.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging_config import get_correlation_id, logger
from app.models.audit_log import AuditLog
from app.models.user import User


def record_action(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    reason: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        actor_role=getattr(actor, "role", None),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        reason=reason,
        before_json=json.dumps(before, ensure_ascii=False) if before is not None else None,
        after_json=json.dumps(after, ensure_ascii=False) if after is not None else None,
        correlation_id=get_correlation_id(),
    )
    db.add(entry)
    db.flush()  # assign id without committing the outer transaction
    logger.info(
        "AUDIT action=%s entity=%s#%s actor=%s",
        action, entity_type, entity_id, getattr(actor, "email", None),
    )
    return entry
