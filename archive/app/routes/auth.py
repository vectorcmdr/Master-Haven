"""
Auth — shared endpoints.

  GET  /api/v1/auth/me     current session user (or 401)
  POST /api/v1/auth/logout clear the session cookie

The dev-login (auth_dev.py) and Discord OAuth (auth_discord.py)
modules expose their own mount points but both produce the same
session cookie that this module reads.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Response

from ..deps import (
    SESSION_COOKIE,
    get_current_user,
    require_login,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me")
def whoami(user: dict = Depends(require_login)):
    """Return the current user. 401 if no valid session."""
    # require_login already raised if no user, so user is non-None
    return {"data": user, "meta": {}}


@router.post("/logout")
def logout(response: Response, user: Optional[dict] = Depends(get_current_user)):
    """
    Clear the session cookie. Idempotent — calling without a session
    still returns 200 (we just delete the cookie either way).
    """
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"data": {"logged_out": True}, "meta": {}}
