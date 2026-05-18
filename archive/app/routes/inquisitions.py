"""
Inquisitions — long-form historical investigations.

GET /api/v1/inquisitions             paginated list
GET /api/v1/inquisitions/{id}        detail with body

Writes come in Phase 4 (publish flow).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import (
    Author,
    Envelope,
    InquisitionDetail,
    InquisitionSummary,
    Meta,
)

router = APIRouter(prefix="/api/v1/inquisitions", tags=["inquisitions"])


def _inq_authors(db: Session, inq_id: int) -> list[Author]:
    rows = db.execute(
        text(
            "SELECT u.id, u.discord_username AS slug, u.display_name AS name, "
            "u.avatar_letter, u.avatar_color, u.base_role AS role "
            "FROM inquisition_author ia "
            "JOIN archive_user u ON u.id = ia.user_id "
            "WHERE ia.inquisition_id = :i "
            "ORDER BY ia.added_at"
        ),
        {"i": inq_id},
    ).fetchall()
    return [
        Author(
            id=r.id, slug=r.slug, name=r.name,
            avatar_letter=r.avatar_letter, avatar_color=r.avatar_color,
            role=r.role,
        )
        for r in rows
    ]


def _inq_civs(db: Session, inq_id: int) -> list[str]:
    rows = db.execute(
        text(
            "SELECT civ_slug FROM inquisition_civilization "
            "WHERE inquisition_id = :i"
        ),
        {"i": inq_id},
    ).fetchall()
    return [r.civ_slug for r in rows]


# ---------------------------------------------------------------------
# GET /api/v1/inquisitions
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[InquisitionSummary]])
def list_inquisitions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    state: str | None = Query(None, regex="^(in_progress|closed|archived)$"),
):
    where = "WHERE deleted_at IS NULL"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if state:
        where += " AND state = :state"
        params["state"] = state

    total = db.execute(
        text(f"SELECT COUNT(*) FROM inquisition {where}"), params
    ).scalar() or 0

    rows = db.execute(
        text(
            f"SELECT id, slug, numeral, title, subtitle, deck, state, "
            f"progress, sources_count, started_at, closed_at "
            f"FROM inquisition {where} "
            f"ORDER BY started_at DESC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()

    summaries = [
        InquisitionSummary(
            id=r.id,
            slug=r.slug,
            numeral=r.numeral,
            title=r.title,
            subtitle=r.subtitle,
            deck=r.deck,
            state=r.state,
            progress=r.progress,
            sources_count=r.sources_count,
            started_at=r.started_at,
            closed_at=r.closed_at,
            authors=_inq_authors(db, r.id),
            civs=_inq_civs(db, r.id),
        )
        for r in rows
    ]
    return Envelope(
        data=summaries,
        meta=Meta(page=page, page_size=page_size, total=total),
    )


# ---------------------------------------------------------------------
# GET /api/v1/inquisitions/{id}
# ---------------------------------------------------------------------
@router.get("/{inq_id}", response_model=Envelope[InquisitionDetail])
def get_inquisition(inq_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT id, slug, numeral, title, subtitle, deck, body, state, "
            "progress, sources_count, started_at, closed_at "
            "FROM inquisition "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": inq_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="inquisition not found")
    return Envelope(data=InquisitionDetail(
        id=row.id,
        slug=row.slug,
        numeral=row.numeral,
        title=row.title,
        subtitle=row.subtitle,
        deck=row.deck,
        body=row.body,
        state=row.state,
        progress=row.progress,
        sources_count=row.sources_count,
        started_at=row.started_at,
        closed_at=row.closed_at,
        authors=_inq_authors(db, row.id),
        civs=_inq_civs(db, row.id),
    ))
