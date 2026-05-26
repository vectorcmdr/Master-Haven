"""
Events — historical events on the master timeline.

  GET    /api/v1/events/{slug}
  POST   /api/v1/events                  historian+ only
  PATCH  /api/v1/events/{slug}           historian+ only
  GET    /api/v1/events/{slug}/revisions
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import get_db, require_historian_or_higher
from ..notifications import notify_watchers
from ..models.schemas import (
    Author,
    Envelope,
    EventDetail,
    EventPatch,
    EventWrite,
    Meta,
    RevisionEntry,
)
from ..revisions import record_revision

router = APIRouter(prefix="/api/v1/events", tags=["events"])


# ---------------------------------------------------------------------
# GET /api/v1/events  — paginated list
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[EventDetail]])
def list_events(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: Optional[str] = Query(None, min_length=2, max_length=120),
    year: Optional[int] = None,
):
    where = "WHERE deleted_at IS NULL"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if q:
        where += " AND (LOWER(title) LIKE :pat OR LOWER(description) LIKE :pat)"
        params["pat"] = f"%{q.lower()}%"
    if year is not None:
        where += " AND event_year = :year"
        params["year"] = year
    total = db.execute(
        text(f"SELECT COUNT(*) FROM event {where}"), params
    ).scalar() or 0
    rows = db.execute(
        text(
            f"SELECT slug, title, event_date, event_year, description "
            f"FROM event {where} "
            f"ORDER BY event_year DESC, title ASC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()
    data = [
        EventDetail(
            slug=r.slug, title=r.title,
            event_date=r.event_date, event_year=r.event_year,
            description=r.description,
        )
        for r in rows
    ]
    return Envelope(
        data=data,
        meta=Meta(page=page, page_size=page_size, total=total, extra={"q": q, "year": year}),
    )


def _event_snapshot(row) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "title": row.title,
        "event_date": row.event_date,
        "event_year": row.event_year,
        "description": row.description,
    }


@router.get("/{slug}", response_model=Envelope[EventDetail])
def get_event(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT slug, title, event_date, event_year, description "
            "FROM event WHERE slug = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    return Envelope(data=EventDetail(
        slug=row.slug, title=row.title,
        event_date=row.event_date, event_year=row.event_year,
        description=row.description,
    ))


@router.post("", response_model=Envelope[EventDetail], status_code=201)
def create_event(
    body: EventWrite,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    if db.execute(text("SELECT 1 FROM event WHERE slug = :s"), {"s": body.slug}).first():
        raise HTTPException(status_code=409, detail=f"slug '{body.slug}' already exists")
    result = db.execute(
        text(
            "INSERT INTO event (slug, title, event_date, event_year, description, created_by) "
            "VALUES (:slug, :title, :event_date, :event_year, :description, :created_by)"
        ),
        {**body.model_dump(), "created_by": user["id"]},
    )
    eid = result.lastrowid
    new_row = db.execute(
        text("SELECT id, slug, title, event_date, event_year, description FROM event WHERE id = :id"),
        {"id": eid},
    ).first()
    record_revision(db, "event", eid, user["id"], "created", _event_snapshot(new_row))
    log_audit(
        db, user["id"], "event.create", "event", eid,
        metadata={"slug": body.slug},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return Envelope(data=EventDetail(
        slug=new_row.slug, title=new_row.title,
        event_date=new_row.event_date, event_year=new_row.event_year,
        description=new_row.description,
    ))


@router.patch("/{slug}", response_model=Envelope[EventDetail])
def patch_event(
    slug: str,
    patch: EventPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    row = db.execute(
        text("SELECT id FROM event WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    # exclude_unset preserves explicit-NULL writes
    fields = patch.model_dump(exclude_unset=True)
    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = row.id
        db.execute(
            text(f"UPDATE event SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            fields,
        )
    new_row = db.execute(
        text("SELECT id, slug, title, event_date, event_year, description FROM event WHERE id = :id"),
        {"id": row.id},
    ).first()
    changed = [k for k in fields.keys() if k != "id"]
    record_revision(db, "event", row.id, user["id"],
                    f"patched {', '.join(changed)}" if changed else "no-op patch",
                    _event_snapshot(new_row))
    log_audit(
        db, user["id"], "event.patch", "event", row.id,
        metadata={"slug": slug, "fields_changed": changed},
        ip_address=request.client.host if request.client else None,
    )
    if changed:
        notify_watchers(
            db, "event", row.id, user["id"],
            title=f"Event updated: {new_row.title}",
            body=f"Fields changed: {', '.join(changed)}",
            link=f"/event/{new_row.slug}",
        )
    db.commit()
    return Envelope(data=EventDetail(
        slug=new_row.slug, title=new_row.title,
        event_date=new_row.event_date, event_year=new_row.event_year,
        description=new_row.description,
    ))


# ---------------------------------------------------------------------
# DELETE /api/v1/events/{slug} — soft-delete (historian+ only)
# ---------------------------------------------------------------------
@router.delete("/{slug}", status_code=204)
def delete_event(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    row = db.execute(
        text("SELECT id FROM event WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    db.execute(
        text("UPDATE event SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": row.id},
    )
    record_revision(db, "event", row.id, user["id"], "deleted", {"slug": slug})
    log_audit(
        db, user["id"], "event.delete", "event", row.id,
        metadata={"slug": slug},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


@router.get("/{slug}/revisions", response_model=Envelope[list[RevisionEntry]])
def list_event_revisions(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id FROM event WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="event not found")
    rows = db.execute(
        text(
            "SELECT r.id, r.change_summary, r.snapshot_json, r.created_at, "
            "u.id AS uid, u.discord_username AS uslug, u.display_name AS uname, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM entity_revision r "
            "LEFT JOIN archive_user u ON u.id = r.changed_by_id "
            "WHERE r.entity_type = 'event' AND r.entity_id = :id "
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
