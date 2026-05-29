"""Pydantic schemas for request/response bodies.

Civ submission itself arrives as multipart/form-data (optional logo file),
so that endpoint parses Form(...) fields directly — see routes/submit.py.
"""

from typing import Literal, Optional

from pydantic import BaseModel

CivStatus = Literal["host", "confirmed", "tentative"]
ApprovalState = Literal["pending", "approved", "rejected"]


class CivPublic(BaseModel):
    """Shape returned to the public site (approved civs only)."""

    id: int
    name: str
    role: str
    description: str
    status: CivStatus
    logo_filename: Optional[str] = None
    logo_url: Optional[str] = None
    discord_link: Optional[str] = None
    display_order: int = 100


class CivAdmin(CivPublic):
    """Full shape for the admin dashboard (includes submitter + workflow fields)."""

    submitter_discord: Optional[str] = None
    submitter_notes: Optional[str] = None
    approval_state: ApprovalState
    created_at: Optional[str] = None
    approved_at: Optional[str] = None
    updated_at: Optional[str] = None


class CivPatch(BaseModel):
    """Admin edit — any subset of these fields may be sent."""

    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CivStatus] = None
    discord_link: Optional[str] = None
    display_order: Optional[int] = None
    approval_state: Optional[ApprovalState] = None


class CreatorCreate(BaseModel):
    """Admin-created creator entry (pure-DB, no sheet origin).

    Time-of-day fields (gmt/est/pst/aest) were removed from the contract — the
    festival sheet exposes them per-row but creators aren't time-bound the way
    scheduled activities are, so the website and admin form no longer surface
    them. The DB columns stay so existing rows aren't broken, just ignored.
    """

    host: str
    event: Optional[str] = ""
    day: Optional[str] = ""
    location: Optional[str] = ""
    link: Optional[str] = ""
    notes: Optional[str] = ""
    display_order: Optional[int] = 100


class CreatorPatch(BaseModel):
    """Admin edit — any subset. Any content field set flips ``admin_edited`` so
    the next sheet sync leaves the row alone. Time fields intentionally omitted
    (see ``CreatorCreate``)."""

    host: Optional[str] = None
    event: Optional[str] = None
    day: Optional[str] = None
    location: Optional[str] = None
    link: Optional[str] = None
    notes: Optional[str] = None
    display_order: Optional[int] = None
    hidden: Optional[int] = None  # 0/1


class AdminLogin(BaseModel):
    password: str


class RejectBody(BaseModel):
    notes: Optional[str] = None
