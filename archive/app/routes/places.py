"""
Places — galactic locations (systems, regions).

  GET    /api/v1/places/{slug}
  POST   /api/v1/places                  historian+ only
  PATCH  /api/v1/places/{slug}           historian+ only
  GET    /api/v1/places/{slug}/revisions
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import get_db, require_historian_or_higher
from ..models.schemas import (
    Author,
    Envelope,
    Meta,
    PlaceDetail,
    PlacePatch,
    PlaceWrite,
    RevisionEntry,
)
from ..revisions import record_revision

router = APIRouter(prefix="/api/v1/places", tags=["places"])


def _place_snapshot(row) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "galaxy": row.galaxy,
        "region": row.region,
        "coordinates": row.coordinates,
        "description": row.description,
    }


@router.get("/{slug}", response_model=Envelope[PlaceDetail])
def get_place(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT slug, name, galaxy, region, coordinates, description "
            "FROM place WHERE slug = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="place not found")
    return Envelope(data=PlaceDetail(
        slug=row.slug, name=row.name, galaxy=row.galaxy, region=row.region,
        coordinates=row.coordinates, description=row.description,
    ))


@router.post("", response_model=Envelope[PlaceDetail], status_code=201)
def create_place(
    body: PlaceWrite,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    if db.execute(text("SELECT 1 FROM place WHERE slug = :s"), {"s": body.slug}).first():
        raise HTTPException(status_code=409, detail=f"slug '{body.slug}' already exists")
    result = db.execute(
        text(
            "INSERT INTO place (slug, name, galaxy, region, coordinates, description, created_by) "
            "VALUES (:slug, :name, :galaxy, :region, :coordinates, :description, :created_by)"
        ),
        {**body.model_dump(), "created_by": user["id"]},
    )
    pid = result.lastrowid
    new_row = db.execute(
        text("SELECT id, slug, name, galaxy, region, coordinates, description FROM place WHERE id = :id"),
        {"id": pid},
    ).first()
    record_revision(db, "place", pid, user["id"], "created", _place_snapshot(new_row))
    log_audit(db, user["id"], "place.create", "place", pid, metadata={"slug": body.slug})
    db.commit()
    return Envelope(data=PlaceDetail(
        slug=new_row.slug, name=new_row.name, galaxy=new_row.galaxy,
        region=new_row.region, coordinates=new_row.coordinates,
        description=new_row.description,
    ))


@router.patch("/{slug}", response_model=Envelope[PlaceDetail])
def patch_place(
    slug: str,
    patch: PlacePatch,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    row = db.execute(
        text("SELECT id FROM place WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="place not found")
    fields = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = row.id
        db.execute(
            text(f"UPDATE place SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            fields,
        )
    new_row = db.execute(
        text("SELECT id, slug, name, galaxy, region, coordinates, description FROM place WHERE id = :id"),
        {"id": row.id},
    ).first()
    record_revision(db, "place", row.id, user["id"],
                    f"patched {', '.join(fields.keys())}" if fields else "no-op patch",
                    _place_snapshot(new_row))
    log_audit(db, user["id"], "place.patch", "place", row.id,
              metadata={"slug": slug, "fields_changed": list(fields.keys())})
    db.commit()
    return Envelope(data=PlaceDetail(
        slug=new_row.slug, name=new_row.name, galaxy=new_row.galaxy,
        region=new_row.region, coordinates=new_row.coordinates,
        description=new_row.description,
    ))


@router.get("/{slug}/revisions", response_model=Envelope[list[RevisionEntry]])
def list_place_revisions(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id FROM place WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="place not found")
    rows = db.execute(
        text(
            "SELECT r.id, r.change_summary, r.snapshot_json, r.created_at, "
            "u.id AS uid, u.discord_username AS uslug, u.display_name AS uname, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM entity_revision r "
            "LEFT JOIN archive_user u ON u.id = r.changed_by_id "
            "WHERE r.entity_type = 'place' AND r.entity_id = :id "
            "ORDER BY r.created_at DESC"
        ),
        {"id": row.id},
    ).fetchall()
    return Envelope(
        data=[
            RevisionEntry(
                id=r.id,
                changed_by=Author(
                    id=r.uid, slug=r.uslug, name=r.uname,
                    avatar_letter=r.avatar_letter, avatar_color=r.avatar_color,
                    role=r.base_role,
                ) if r.uid else Author(id=0, slug="system", name="system"),
                change_summary=r.change_summary,
                snapshot=json.loads(r.snapshot_json) if r.snapshot_json else {},
                created_at=r.created_at,
            )
            for r in rows
        ],
        meta=Meta(total=len(rows), extra={"slug": slug}),
    )
