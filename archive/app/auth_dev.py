"""
Dev-only fake login.

Endpoints:
  GET  /api/v1/auth/dev/users    list seeded users you can log in as
  POST /api/v1/auth/dev/login    {user_id: int} → sets session cookie

Shared auth endpoints (logout, me) live in routes/auth.py and work
the same regardless of which login path produced the session.

All endpoints in this module return 404 in production. Gated by
config.is_dev — if you flip ENV=production and try to hit these, you
get a clean 404 with detail="not available in production".

Adding a new dev user: append a row to the seed in app/seed.py and
rebuild. The dev-login picker reads from archive_user, so it
auto-updates.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .deps import (
    SESSION_COOKIE,
    SESSION_MAX_AGE_SECONDS,
    get_db,
    make_session_token,
)

log = logging.getLogger("archive.auth_dev")

# Mounted under /api/v1/auth via include_router below
router = APIRouter(prefix="/api/v1/auth/dev", tags=["auth-dev"])


def _ensure_dev_mode() -> None:
    """Raise 404 if not in dev — used by all dev endpoints."""
    if not get_settings().is_dev:
        raise HTTPException(
            status_code=404,
            detail="not available in production",
        )


# ---------------------------------------------------------------------
# request models
# ---------------------------------------------------------------------
class DevLoginRequest(BaseModel):
    user_id: int


# ---------------------------------------------------------------------
# GET /api/v1/auth/dev/users — list pickable users
# ---------------------------------------------------------------------
@router.get("/users")
def list_dev_users(db: Session = Depends(get_db)):
    """
    Return every seeded user so the dev picker can offer them. Sorted
    by base_role (admin first, then historian, diplomat, reader) then
    name for stable order in the UI.
    """
    _ensure_dev_mode()
    rows = db.execute(
        text(
            "SELECT id, discord_username, display_name, avatar_letter, "
            "avatar_color, civ_slug, beat, base_role, is_editor, is_admin "
            "FROM archive_user "
            "WHERE deleted_at IS NULL "
            "ORDER BY is_admin DESC, "
            "CASE base_role "
            "  WHEN 'historian' THEN 1 "
            "  WHEN 'diplomat' THEN 2 "
            "  ELSE 3 END, "
            "display_name"
        )
    ).fetchall()
    data = [
        {
            "id": r.id,
            "slug": r.discord_username,
            "name": r.display_name,
            "avatar_letter": r.avatar_letter,
            "avatar_color": r.avatar_color,
            "civ_slug": r.civ_slug,
            "beat": r.beat,
            "base_role": r.base_role,
            "is_editor": bool(r.is_editor),
            "is_admin": bool(r.is_admin),
        }
        for r in rows
    ]
    return {"data": data, "meta": {"total": len(data)}}


# ---------------------------------------------------------------------
# POST /api/v1/auth/dev/login — set the session cookie
# ---------------------------------------------------------------------
@router.post("/login")
def dev_login(
    body: DevLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Pick a user from the seeded list. Sets archive_session cookie."""
    _ensure_dev_mode()
    user = db.execute(
        text(
            "SELECT id, discord_username, display_name, base_role "
            "FROM archive_user "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": body.user_id},
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    token = make_session_token(user.id)
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.is_production,    # http in dev, https in prod
        samesite="lax",
        path="/",
    )
    # Update last_login (best-effort; tracks who's actively using dev mode)
    db.execute(
        text("UPDATE archive_user SET last_login = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": user.id},
    )
    db.commit()
    log.info("dev-login as %s (id=%d)", user.discord_username, user.id)
    return {
        "data": {
            "id": user.id,
            "slug": user.discord_username,
            "name": user.display_name,
            "base_role": user.base_role,
        },
        "meta": {},
    }
