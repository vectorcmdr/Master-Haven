"""
Places — galactic locations (systems, regions).

GET /api/v1/places/{slug}   single place detail

Phase 2: no seed places yet. Endpoint exists so the URL surface is
stable for Phase 5 frontend wiring; populated by Phase 4 writes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import Envelope, PlaceDetail

router = APIRouter(prefix="/api/v1/places", tags=["places"])


@router.get("/{slug}", response_model=Envelope[PlaceDetail])
def get_place(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT slug, name, galaxy, region, coordinates, description "
            "FROM place "
            "WHERE slug = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="place not found")
    return Envelope(data=PlaceDetail(
        slug=row.slug,
        name=row.name,
        galaxy=row.galaxy,
        region=row.region,
        coordinates=row.coordinates,
        description=row.description,
    ))
