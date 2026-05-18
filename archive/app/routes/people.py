"""
People — encyclopedia entries.

GET /api/v1/people/{slug}

`slug` matches `archive_user.discord_username` (which is what we use
as the URL handle for any logged-in user) OR `person.slug` for
historical people who have a person page but no Discord account.

Phase 2 only ships the archive_user lookup since that's what the
mockup's persona pages render. The person table is fed by Phase 4
writes once entity editing is in.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import Envelope, PersonDetail

router = APIRouter(prefix="/api/v1/people", tags=["people"])


@router.get("/{slug}", response_model=Envelope[PersonDetail])
def get_person(slug: str, db: Session = Depends(get_db)):
    # First try the person table (for historical figures not on Discord)
    row = db.execute(
        text(
            "SELECT slug, name, discord_username, civ_slug, role_in_civ, bio "
            "FROM person "
            "WHERE slug = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if row:
        return Envelope(data=PersonDetail(
            slug=row.slug,
            name=row.name,
            discord_username=row.discord_username,
            civ_slug=row.civ_slug,
            role_in_civ=row.role_in_civ,
            bio=row.bio,
        ))
    # Fall through to archive_user lookup
    row = db.execute(
        text(
            "SELECT discord_username AS slug, display_name AS name, "
            "discord_username, civ_slug, NULL AS role_in_civ, bio "
            "FROM archive_user "
            "WHERE discord_username = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    return Envelope(data=PersonDetail(
        slug=row.slug,
        name=row.name,
        discord_username=row.discord_username,
        civ_slug=row.civ_slug,
        role_in_civ=row.role_in_civ,
        bio=row.bio,
    ))
