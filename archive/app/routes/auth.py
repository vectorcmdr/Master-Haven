"""
Auth — shared endpoints (login/logout/me).

Phase 3 mounts the dev-only fake-login endpoints from app/auth_dev.py
under this router. Phase 7 adds the Discord OAuth flow from
app/auth_discord.py.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
