"""
Travelers Exchange — Authentication Routes

Provides registration, login, and logout endpoints under ``/api/auth``.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import (
    create_session,
    delete_session,
    get_current_user,
    hash_password,
    require_login,
    verify_api_key,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import ApiKey, DiscordLinkCode, User
from app.wallet import generate_wallet_address

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Cookie configuration
COOKIE_KEY = "session_token"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds


def _set_session_cookie(response: Response, token: str) -> None:
    """Apply the session cookie to *response* with standard settings.

    NOTE on `secure=True`: cookies marked Secure are only sent by browsers
    over HTTPS.  Production runs behind Cloudflare → Nginx Proxy Manager
    with TLS termination so this is correct there.  In a plain-HTTP local
    dev setup (e.g. running the container on http://localhost:8010 without
    a proxy), real browsers will refuse to *store* the cookie at all and
    every request will appear unauthenticated.  Workarounds for local dev:
      1. Run the dev container behind an HTTPS proxy (e.g. mkcert + caddy).
      2. Temporarily flip secure=False here for local-only debugging.
    A future hardening pass should gate this on an env var (e.g.
    `settings.COOKIE_SECURE`) so the same code base works in both modes
    without requiring a manual toggle.
    """
    response.set_cookie(
        key=COOKIE_KEY,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # TEMP for local-dev demo — flip back to True before merging
        max_age=COOKIE_MAX_AGE,
    )


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

@router.post("/register")
def register(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    email: str = Form(None),
    display_name: str = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """Register a new user account.

    Accepts form-encoded data, validates inputs, creates the user with a
    wallet address, starts a session, and returns the wallet address.
    """
    # --- Validation ---
    if not username or not username.strip():
        return {"success": False, "error": "Username is required"}

    username = username.strip()

    if len(password) < 8:
        return {"success": False, "error": "Password must be at least 8 characters"}

    if password != confirm_password:
        return {"success": False, "error": "Passwords do not match"}

    # Check uniqueness
    stmt = select(User).where(User.username == username)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return {"success": False, "error": "Username already taken"}

    # --- Create user (without wallet address first) ---
    hashed_pw = hash_password(password)

    new_user = User(
        username=username,
        password_hash=hashed_pw,
        email=email or None,
        display_name=display_name or None,
        wallet_address="PENDING",  # placeholder — will be replaced after flush
        role="citizen",
        balance=0,
    )
    db.add(new_user)
    db.flush()  # assigns new_user.id without committing

    # Generate wallet address from the real user ID
    wallet_address = generate_wallet_address(new_user.id, settings.SECRET_KEY)
    new_user.wallet_address = wallet_address

    db.commit()

    # --- Start session ---
    token = create_session(db, new_user.id)
    _set_session_cookie(response, token)

    return {"success": True, "wallet_address": wallet_address}


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@router.post("/login")
def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> dict:
    """Authenticate an existing user.

    Verifies credentials, creates a new session, and sets the session
    cookie.
    """
    # Clear any existing session first (so switching accounts works cleanly)
    old_token = request.cookies.get(COOKIE_KEY)
    if old_token:
        delete_session(db, old_token)

    stmt = select(User).where(User.username == username)
    user = db.execute(stmt).scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        return {"success": False, "error": "Invalid username or password"}

    token = create_session(db, user.id)
    _set_session_cookie(response, token)

    return {"success": True}


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """End the current user session.

    Removes the session from the database and clears the cookie.
    """
    token = request.cookies.get(COOKIE_KEY)
    if token:
        delete_session(db, token)

    response.delete_cookie(
        key=COOKIE_KEY,
        httponly=True,
        samesite="lax",
        secure=True,
    )

    return {"success": True}


# ===========================================================================
# Keeper integration P0 — Discord identity binding
# ===========================================================================
#
# Three endpoints implement the link flow described in
# EXCHANGE_KEEPER_INTEGRATION_SPEC.md §5 "/exchange link":
#
#   POST   /api/auth/discord-link/start    — bot-only.  Returns a 6-digit
#                                            code valid for 10 minutes.
#   POST   /api/auth/discord-link/confirm  — session-auth.  User pastes
#                                            the code on the website.
#   DELETE /api/auth/discord-link          — session-auth.  Unlink.
#
# The code is short and human-typeable (six decimal digits).  Codes are
# rotated whenever start is called for the same discord_id, so a fresh
# code always supersedes any in-flight one.

LINK_CODE_TTL_SECONDS = 10 * 60


class DiscordLinkStartRequest(BaseModel):
    discord_id: str


@router.post("/discord-link/start")
def discord_link_start(
    payload: DiscordLinkStartRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Bot-only.  Issue a 6-digit code that the user will paste into the
    Exchange website to bind their Discord ID to their Exchange account.

    Auth: ``Authorization: Bearer <KEEPER_API_KEY>`` only — no
    X-Discord-User-Id header (the discord_id is in the body).
    """
    # Verify bot key — this endpoint cannot use get_current_user because
    # the bot isn't acting on behalf of a linked user yet.
    auth_hdr = request.headers.get("authorization") or ""
    if not auth_hdr.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bot bearer token required.")
    token = auth_hdr.split(None, 1)[1].strip()
    api_key = verify_api_key(token, db)
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid bot bearer token.")

    discord_id = (payload.discord_id or "").strip()
    if not discord_id:
        raise HTTPException(status_code=400, detail="discord_id is required.")

    # Reject if this discord_id is already linked to an Exchange user.
    already = db.execute(
        select(User).where(User.discord_id == discord_id)
    ).scalar_one_or_none()
    if already is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Discord ID is already linked to Exchange user '{already.username}'.",
        )

    # Rotate any prior in-flight code for this discord_id.
    db.execute(
        delete(DiscordLinkCode).where(DiscordLinkCode.discord_id == discord_id)
    )

    # Generate a fresh 6-digit code (zero-padded).  Use secrets for
    # cryptographic randomness even though 6 digits is only ~20 bits;
    # combined with the 10-minute TTL it's good enough for a one-shot
    # binding handshake.
    code = f"{secrets.randbelow(1_000_000):06d}"

    db.add(
        DiscordLinkCode(
            code=code,
            discord_id=discord_id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=LINK_CODE_TTL_SECONDS),
        )
    )
    db.commit()

    return {
        "code": code,
        "expires_in": LINK_CODE_TTL_SECONDS,
        "link_url": f"https://travelers-exchange.online/settings#link-discord",
    }


@router.post("/discord-link/confirm")
def discord_link_confirm(
    code: str = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
) -> dict:
    """Session-auth.  User pastes the 6-digit code from the bot into the
    /settings page.  Server binds discord_id to the calling user.
    """
    # Block double-binding from the user side — if they already have a
    # discord_id, they should unlink first.
    if user.discord_id:
        raise HTTPException(
            status_code=409,
            detail="Your account is already linked to a Discord ID. Unlink first.",
        )

    code = (code or "").strip()
    if not code or len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="Code must be 6 digits.")

    row = db.execute(
        select(DiscordLinkCode).where(DiscordLinkCode.code == code)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Code not found or already used.")

    # Check expiry (handle naive datetimes from SQLite as UTC).
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        db.execute(delete(DiscordLinkCode).where(DiscordLinkCode.id == row.id))
        db.commit()
        raise HTTPException(status_code=410, detail="Code has expired. Re-run /exchange link in Discord.")

    # Defensive: another Exchange user may have linked this discord_id
    # between code-issue and confirm (race window is small but real).
    clash = db.execute(
        select(User).where(User.discord_id == row.discord_id, User.id != user.id)
    ).scalar_one_or_none()
    if clash is not None:
        db.execute(delete(DiscordLinkCode).where(DiscordLinkCode.id == row.id))
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="This Discord ID is already linked to another Exchange account.",
        )

    user.discord_id = row.discord_id
    db.execute(delete(DiscordLinkCode).where(DiscordLinkCode.id == row.id))
    db.commit()

    return {"success": True, "discord_id": row.discord_id}


@router.delete("/discord-link")
def discord_link_delete(
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
) -> dict:
    """Session-auth.  Unlink the calling user's Discord binding."""
    if not user.discord_id:
        raise HTTPException(status_code=404, detail="Your account has no Discord link.")
    user.discord_id = None
    db.commit()
    return {"success": True}
