"""
Timeline — master mixed-stream timeline.

GET /api/v1/timeline   merged events + story dates + inquisition starts +
                       civ founded/ended markers

The mockup's master timeline page renders one row per civ-lane plus a
horizontal axis for each year. This endpoint hands the frontend the
full unsorted-by-civ stream; the frontend bins by year/lane on its end.

Future filter knobs (Phase 4+): ?year_from=, ?year_to=, ?civ=, ?kind=.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import Envelope, Meta, TimelineEntry

router = APIRouter(prefix="/api/v1/timeline", tags=["timeline"])


def _year_of(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).year
    except ValueError:
        return None


@router.get("", response_model=Envelope[list[TimelineEntry]])
def list_timeline(
    db: Session = Depends(get_db),
    limit: int = Query(500, ge=1, le=2000),
):
    entries: list[TimelineEntry] = []

    # --- historical events (will be empty until Phase 4 entity edits) ---
    rows = db.execute(
        text(
            "SELECT slug, title, event_date, event_year "
            "FROM event WHERE deleted_at IS NULL"
        )
    ).fetchall()
    for r in rows:
        entries.append(TimelineEntry(
            kind="event",
            date=r.event_date or (str(r.event_year) if r.event_year else ""),
            year=r.event_year,
            title=r.title,
            slug=r.slug,
        ))

    # --- story publication dates ---
    rows = db.execute(
        text(
            "SELECT s.id, s.slug, s.doctype, s.headline, s.published_at "
            "FROM story s "
            "WHERE s.deleted_at IS NULL"
        )
    ).fetchall()
    for r in rows:
        civs = [
            x.civ_slug for x in db.execute(
                text("SELECT civ_slug FROM story_civilization WHERE story_id = :sid"),
                {"sid": r.id},
            ).fetchall()
        ]
        entries.append(TimelineEntry(
            kind="story",
            date=r.published_at,
            year=_year_of(r.published_at),
            title=r.headline,
            slug=r.slug,
            id=r.id,
            doctype=r.doctype,
            civs=civs,
        ))

    # --- inquisition start dates ---
    rows = db.execute(
        text(
            "SELECT id, slug, numeral, title, started_at "
            "FROM inquisition WHERE deleted_at IS NULL"
        )
    ).fetchall()
    for r in rows:
        civs = [
            x.civ_slug for x in db.execute(
                text("SELECT civ_slug FROM inquisition_civilization WHERE inquisition_id = :i"),
                {"i": r.id},
            ).fetchall()
        ]
        entries.append(TimelineEntry(
            kind="inquisition",
            date=r.started_at,
            year=_year_of(r.started_at),
            title=f"Inquisition {r.numeral}: {r.title}",
            slug=r.slug,
            id=r.id,
            doctype="inquisition",
            civs=civs,
        ))

    # --- civ founding + ending markers ---
    rows = db.execute(
        text(
            "SELECT slug, name, founded, founded_year, ended, ended_year "
            "FROM civilization WHERE deleted_at IS NULL"
        )
    ).fetchall()
    for r in rows:
        if r.founded_year:
            entries.append(TimelineEntry(
                kind="civ-founded",
                date=r.founded or str(r.founded_year),
                year=r.founded_year,
                title=f"{r.name} founded",
                slug=r.slug,
                civs=[r.slug],
            ))
        if r.ended_year:
            entries.append(TimelineEntry(
                kind="civ-ended",
                date=r.ended or str(r.ended_year),
                year=r.ended_year,
                title=f"{r.name} ended",
                slug=r.slug,
                civs=[r.slug],
            ))

    # Sort newest-first by date string (ISO dates sort correctly as strings)
    entries.sort(key=lambda e: e.date or "", reverse=True)
    entries = entries[:limit]

    return Envelope(
        data=entries,
        meta=Meta(total=len(entries)),
    )
