"""
Civilizations — encyclopedia entries.

Read endpoints (Phase 2):
  GET /api/v1/civilizations                  paginated list (summary cards)
  GET /api/v1/civilizations/{slug}           single civ (detail)
  GET /api/v1/civilizations/{slug}/coverage  stories + inquisitions tagged with this civ

Write endpoints come in Phase 4.

Field shapes mirror the v0.9 mockup's CIVS objects so Phase 5 can
render civ cards / civ pages without any client-side reshaping.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import (
    Author,
    CivStats,
    CivilizationDetail,
    CivilizationSummary,
    CoverageItem,
    Envelope,
    Meta,
)

router = APIRouter(prefix="/api/v1/civilizations", tags=["civilizations"])


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------
def _row_to_summary(row, stats: CivStats) -> CivilizationSummary:
    """Build a CivilizationSummary from a SELECT * row."""
    return CivilizationSummary(
        slug=row.slug,
        name=row.name,
        status=row.status,
        galaxy=row.galaxy,
        founded=row.founded,
        ended=row.ended,
        tagline=row.tagline,
        color_primary=row.color_primary,
        color_secondary=row.color_secondary,
        stats=stats,
    )


def _compute_stats(db: Session, civ_slug: str, founded_year: int | None, ended_year: int | None) -> CivStats:
    """
    Compute live counts for a civ's stat strip.

    `entries` = stories tagged with this civ + inquisitions tagged with this civ
    `inquisitions` = inquisitions tagged with this civ
    `people` = archive_user rows whose primary civ_slug matches
    `years` = founded → ended (or current year, 2026) span
    """
    story_count = db.execute(
        text("SELECT COUNT(*) FROM story_civilization WHERE civ_slug = :s"),
        {"s": civ_slug},
    ).scalar() or 0
    inq_count = db.execute(
        text("SELECT COUNT(*) FROM inquisition_civilization WHERE civ_slug = :s"),
        {"s": civ_slug},
    ).scalar() or 0
    people_count = db.execute(
        text(
            "SELECT COUNT(*) FROM archive_user "
            "WHERE civ_slug = :s AND deleted_at IS NULL"
        ),
        {"s": civ_slug},
    ).scalar() or 0
    # Years active. If still active, use current archive year (2026).
    years = 0
    if founded_year is not None:
        end = ended_year if ended_year else 2026
        years = max(0, end - founded_year)
    return CivStats(
        entries=story_count + inq_count,
        inquisitions=inq_count,
        people=people_count,
        years=years,
    )


# ---------------------------------------------------------------------
# GET /api/v1/civilizations
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[CivilizationSummary]])
def list_civilizations(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: str | None = Query(None, regex="^(active|dormant|archived)$"),
):
    """Paginated list of civilizations. Optional status filter."""
    where = "WHERE deleted_at IS NULL"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if status:
        where += " AND status = :status"
        params["status"] = status

    total = db.execute(
        text(f"SELECT COUNT(*) FROM civilization {where}"), params
    ).scalar() or 0

    rows = db.execute(
        text(
            f"SELECT slug, name, status, galaxy, founded, founded_year, "
            f"ended, ended_year, tagline, color_primary, color_secondary "
            f"FROM civilization {where} "
            f"ORDER BY founded_year DESC, name ASC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()

    summaries = [
        _row_to_summary(r, _compute_stats(db, r.slug, r.founded_year, r.ended_year))
        for r in rows
    ]
    return Envelope(
        data=summaries,
        meta=Meta(page=page, page_size=page_size, total=total),
    )


# ---------------------------------------------------------------------
# GET /api/v1/civilizations/{slug}
# ---------------------------------------------------------------------
@router.get("/{slug}", response_model=Envelope[CivilizationDetail])
def get_civilization(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT slug, name, status, galaxy, founded, founded_year, "
            "ended, ended_year, tagline, description, "
            "color_primary, color_secondary "
            "FROM civilization "
            "WHERE slug = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="civilization not found")
    stats = _compute_stats(db, row.slug, row.founded_year, row.ended_year)
    detail = CivilizationDetail(
        slug=row.slug,
        name=row.name,
        status=row.status,
        galaxy=row.galaxy,
        founded=row.founded,
        founded_year=row.founded_year,
        ended=row.ended,
        ended_year=row.ended_year,
        tagline=row.tagline,
        description=row.description,
        color_primary=row.color_primary,
        color_secondary=row.color_secondary,
        stats=stats,
    )
    return Envelope(data=detail)


# ---------------------------------------------------------------------
# GET /api/v1/civilizations/{slug}/coverage
# ---------------------------------------------------------------------
@router.get("/{slug}/coverage", response_model=Envelope[list[CoverageItem]])
def civilization_coverage(
    slug: str,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """
    All coverage tagged with this civ, sorted newest first.

    Returns a mixed list of stories and inquisitions. The 'kind' field
    tells the frontend which page to route to on click.
    """
    # Verify civ exists (so we don't return [] for a typo'd slug)
    exists = db.execute(
        text("SELECT 1 FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="civilization not found")

    items: list[CoverageItem] = []

    # Stories
    story_rows = db.execute(
        text(
            "SELECT s.id, s.slug, s.doctype, s.headline, s.deck, s.beat, "
            "s.published_at, s.author_id, "
            "u.discord_username AS author_slug, u.display_name AS author_name, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM story s "
            "JOIN story_civilization sc ON sc.story_id = s.id "
            "LEFT JOIN archive_user u ON u.id = s.author_id "
            "WHERE sc.civ_slug = :s AND s.deleted_at IS NULL "
            "ORDER BY s.published_at DESC LIMIT :lim"
        ),
        {"s": slug, "lim": limit},
    ).fetchall()
    for r in story_rows:
        items.append(CoverageItem(
            kind="story",
            id=r.id,
            slug=r.slug,
            doctype=r.doctype,
            headline=r.headline,
            deck=r.deck,
            beat=r.beat,
            published_at=r.published_at,
            author=Author(
                id=r.author_id,
                slug=r.author_slug,
                name=r.author_name,
                avatar_letter=r.avatar_letter,
                avatar_color=r.avatar_color,
                role=r.base_role,
            ) if r.author_id else None,
        ))

    # Inquisitions
    inq_rows = db.execute(
        text(
            "SELECT i.id, i.slug, i.numeral, i.title, i.subtitle, i.deck, "
            "i.state, i.started_at, i.lead_author_id, "
            "u.discord_username AS author_slug, u.display_name AS author_name, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM inquisition i "
            "JOIN inquisition_civilization ic ON ic.inquisition_id = i.id "
            "LEFT JOIN archive_user u ON u.id = i.lead_author_id "
            "WHERE ic.civ_slug = :s AND i.deleted_at IS NULL "
            "ORDER BY i.started_at DESC LIMIT :lim"
        ),
        {"s": slug, "lim": limit},
    ).fetchall()
    for r in inq_rows:
        items.append(CoverageItem(
            kind="inquisition",
            id=r.id,
            slug=r.slug,
            doctype="inquisition",
            headline=f"Inquisition {r.numeral}: {r.title}",
            deck=r.deck or r.subtitle,
            numeral=r.numeral,
            state=r.state,
            started_at=r.started_at,
            author=Author(
                id=r.lead_author_id,
                slug=r.author_slug,
                name=r.author_name,
                avatar_letter=r.avatar_letter,
                avatar_color=r.avatar_color,
                role=r.base_role,
            ) if r.lead_author_id else None,
        ))

    # Sort all items newest-first (use whichever date column populates)
    def _sort_key(c: CoverageItem) -> str:
        return c.published_at or c.started_at or ""
    items.sort(key=_sort_key, reverse=True)
    items = items[:limit]

    return Envelope(
        data=items,
        meta=Meta(total=len(items), extra={"civ": slug}),
    )
