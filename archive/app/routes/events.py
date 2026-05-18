"""
Events — historical events on the master timeline.

GET /api/v1/events/{slug}   single event detail

Phase 2: no seed events yet (the mockup's timeline mixes story dates
and civ founding dates without dedicated event objects). This
endpoint will return real data once Phase 4 entity edits start
populating the `event` table.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import Envelope, EventDetail

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("/{slug}", response_model=Envelope[EventDetail])
def get_event(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT slug, title, event_date, event_year, description "
            "FROM event "
            "WHERE slug = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    return Envelope(data=EventDetail(
        slug=row.slug,
        title=row.title,
        event_date=row.event_date,
        event_year=row.event_year,
        description=row.description,
    ))
