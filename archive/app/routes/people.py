"""
People — encyclopedia entries.

  GET    /api/v1/people/{slug}
  POST   /api/v1/people                  historian+ only
  PATCH  /api/v1/people/{slug}           historian+ only; records revision
  GET    /api/v1/people/{slug}/revisions

`slug` matches person.slug for historical people. Live Discord users
(archive_user) are also resolvable via this endpoint as a convenience
so the frontend can route /profile/{discord_username} to /people/{slug}
without a separate lookup.
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
    PersonDetail,
    PersonPatch,
    PersonWrite,
    RevisionEntry,
)
from ..revisions import record_revision

router = APIRouter(prefix="/api/v1/people", tags=["people"])


def _person_snapshot(row) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "discord_username": row.discord_username,
        "civ_slug": row.civ_slug,
        "role_in_civ": row.role_in_civ,
        "bio": row.bio,
    }


# ---------------------------------------------------------------------
# GET /api/v1/people/{slug}
# ---------------------------------------------------------------------
@router.get("/{slug}", response_model=Envelope[PersonDetail])
def get_person(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT slug, name, discord_username, civ_slug, role_in_civ, bio "
            "FROM person WHERE slug = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if row:
        return Envelope(data=PersonDetail(
            slug=row.slug, name=row.name, discord_username=row.discord_username,
            civ_slug=row.civ_slug, role_in_civ=row.role_in_civ, bio=row.bio,
        ))
    # Fall through to archive_user (Discord identity as a person)
    row = db.execute(
        text(
            "SELECT discord_username AS slug, display_name AS name, "
            "discord_username, civ_slug, NULL AS role_in_civ, bio "
            "FROM archive_user WHERE discord_username = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    return Envelope(data=PersonDetail(
        slug=row.slug, name=row.name, discord_username=row.discord_username,
        civ_slug=row.civ_slug, role_in_civ=row.role_in_civ, bio=row.bio,
    ))


# ---------------------------------------------------------------------
# POST /api/v1/people  — historian+ only
# ---------------------------------------------------------------------
@router.post("", response_model=Envelope[PersonDetail], status_code=201)
def create_person(
    body: PersonWrite,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    if db.execute(text("SELECT 1 FROM person WHERE slug = :s"), {"s": body.slug}).first():
        raise HTTPException(status_code=409, detail=f"slug '{body.slug}' already exists")
    result = db.execute(
        text(
            "INSERT INTO person (slug, name, discord_username, civ_slug, "
            "role_in_civ, bio, created_by) "
            "VALUES (:slug, :name, :discord_username, :civ_slug, "
            ":role_in_civ, :bio, :created_by)"
        ),
        {**body.model_dump(), "created_by": user["id"]},
    )
    pid = result.lastrowid
    new_row = db.execute(
        text(
            "SELECT id, slug, name, discord_username, civ_slug, role_in_civ, bio "
            "FROM person WHERE id = :id"
        ),
        {"id": pid},
    ).first()
    record_revision(db, "person", pid, user["id"], "created", _person_snapshot(new_row))
    log_audit(db, user["id"], "person.create", "person", pid, metadata={"slug": body.slug})
    db.commit()
    return Envelope(data=PersonDetail(
        slug=new_row.slug, name=new_row.name,
        discord_username=new_row.discord_username, civ_slug=new_row.civ_slug,
        role_in_civ=new_row.role_in_civ, bio=new_row.bio,
    ))


# ---------------------------------------------------------------------
# PATCH /api/v1/people/{slug}  — historian+ only
# ---------------------------------------------------------------------
@router.patch("/{slug}", response_model=Envelope[PersonDetail])
def patch_person(
    slug: str,
    patch: PersonPatch,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    row = db.execute(
        text("SELECT id FROM person WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    fields = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = row.id
        db.execute(
            text(f"UPDATE person SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            fields,
        )
    new_row = db.execute(
        text(
            "SELECT id, slug, name, discord_username, civ_slug, role_in_civ, bio "
            "FROM person WHERE id = :id"
        ),
        {"id": row.id},
    ).first()
    record_revision(db, "person", row.id, user["id"],
                    f"patched {', '.join(fields.keys())}" if fields else "no-op patch",
                    _person_snapshot(new_row))
    log_audit(db, user["id"], "person.patch", "person", row.id,
              metadata={"slug": slug, "fields_changed": list(fields.keys())})
    db.commit()
    return Envelope(data=PersonDetail(
        slug=new_row.slug, name=new_row.name,
        discord_username=new_row.discord_username, civ_slug=new_row.civ_slug,
        role_in_civ=new_row.role_in_civ, bio=new_row.bio,
    ))


# ---------------------------------------------------------------------
# GET /api/v1/people/{slug}/revisions
# ---------------------------------------------------------------------
@router.get("/{slug}/revisions", response_model=Envelope[list[RevisionEntry]])
def list_person_revisions(slug: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id FROM person WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    rows = db.execute(
        text(
            "SELECT r.id, r.change_summary, r.snapshot_json, r.created_at, "
            "u.id AS uid, u.discord_username AS uslug, u.display_name AS uname, "
            "u.avatar_letter, u.avatar_color, u.base_role "
            "FROM entity_revision r "
            "LEFT JOIN archive_user u ON u.id = r.changed_by_id "
            "WHERE r.entity_type = 'person' AND r.entity_id = :id "
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
