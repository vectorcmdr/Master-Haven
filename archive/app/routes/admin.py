"""
Admin — super-admin-only operational endpoints.

  GET /api/v1/admin/audit_log    recent audit_log entries (admin only)

Phase 4: only the audit log read is wired (the test script checks
that publish/return/etc. write audit entries). More admin endpoints
(user role management, Discord sync log read) come in later phases.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db, require_admin

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/audit_log")
def audit_log(
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
    limit: int = Query(100, ge=1, le=500),
    action: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
):
    """Read recent audit log entries. Filter by action, target_type, target_id."""
    where = "WHERE 1=1"
    params: dict = {"limit": limit}
    if action:
        where += " AND action = :action"
        params["action"] = action
    if target_type:
        where += " AND target_type = :tt"
        params["tt"] = target_type
    if target_id is not None:
        where += " AND target_id = :tid"
        params["tid"] = target_id
    rows = db.execute(
        text(
            f"SELECT a.id, a.user_id, u.display_name AS user_name, "
            f"a.action, a.target_type, a.target_id, a.metadata_json, "
            f"a.ip_address, a.created_at "
            f"FROM audit_log a "
            f"LEFT JOIN archive_user u ON u.id = a.user_id "
            f"{where} ORDER BY a.created_at DESC LIMIT :limit"
        ),
        params,
    ).fetchall()
    data = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "user_name": r.user_name,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "metadata": json.loads(r.metadata_json) if r.metadata_json else None,
            "ip_address": r.ip_address,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return {"data": data, "meta": {"total": len(data)}}
