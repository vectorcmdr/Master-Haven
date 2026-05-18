"""
Audit log helper.

Every meaningful state transition (publish, return, mark_ready, role
change, content delete, entity create/edit) writes a row to audit_log.

Keep this dead simple — a single helper that takes a session and the
fields. Callers pass a dict for metadata; we json.dumps it.

The audit log is read-only from the API perspective (admin views it
via /api/v1/admin/audit_log; never edited or deleted).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def log_audit(
    db: Session,
    user_id: Optional[int],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Insert an audit_log row. Does NOT commit — caller controls txn."""
    db.execute(
        text(
            "INSERT INTO audit_log (user_id, action, target_type, target_id, "
            "metadata_json, ip_address) "
            "VALUES (:uid, :action, :tt, :tid, :meta, :ip)"
        ),
        {
            "uid": user_id,
            "action": action,
            "tt": target_type,
            "tid": target_id,
            "meta": json.dumps(metadata) if metadata else None,
            "ip": ip_address,
        },
    )
