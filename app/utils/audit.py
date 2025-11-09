"""Audit logging helpers."""

from __future__ import annotations

from typing import Any

from .. import db
from ..models import AuditLog, User


def log_audit(action: str, target_type: str, target_id: str, metadata: dict[str, Any] | None = None, user: User | None = None) -> None:
    entry = AuditLog(
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata or {},
        user_id=user.id if user else None,
    )
    db.session.add(entry)
    db.session.commit()
