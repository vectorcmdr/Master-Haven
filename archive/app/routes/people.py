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
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import get_db, get_current_user, require_historian_or_higher
from ..notifications import notify_watchers
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


# ---------------------------------------------------------------------
# GET /api/v1/people  — paginated list
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[PersonDetail]])
def list_people(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: Optional[str] = Query(None, min_length=2, max_length=120),
    civ_slug: Optional[str] = None,
):
    where = "WHERE deleted_at IS NULL"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if q:
        where += " AND (LOWER(name) LIKE :pat OR LOWER(slug) LIKE :pat OR LOWER(bio) LIKE :pat)"
        params["pat"] = f"%{q.lower()}%"
    if civ_slug:
        where += " AND civ_slug = :civ"
        params["civ"] = civ_slug
    total = db.execute(
        text(f"SELECT COUNT(*) FROM person {where}"), params
    ).scalar() or 0
    rows = db.execute(
        text(
            f"SELECT slug, name, discord_username, civ_slug, role_in_civ, bio "
            f"FROM person {where} "
            f"ORDER BY name ASC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()
    data = [
        PersonDetail(
            slug=r.slug, name=r.name, discord_username=r.discord_username,
            civ_slug=r.civ_slug, role_in_civ=r.role_in_civ, bio=r.bio,
        )
        for r in rows
    ]
    return Envelope(
        data=data,
        meta=Meta(page=page, page_size=page_size, total=total, extra={"q": q, "civ_slug": civ_slug}),
    )


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
def get_person(
    slug: str,
    db: Session = Depends(get_db),
    user: Optional[dict] = Depends(get_current_user),
):
    """
    Resolve a person slug. First tries the curated `person` table
    (encyclopedia entries); falls back to `archive_user` (live Discord
    identity).

    The archive_user fallback is gated behind a session — without that
    gate the endpoint was a public user-enumeration surface (anyone
    could probe random discord usernames and discover which exist).
    """
    row = db.execute(
        text(
            "SELECT person.slug, person.name, person.discord_username, "
            "person.civ_slug, person.role_in_civ, person.bio "
            "FROM person "
            "WHERE person.slug = :s AND person.deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if row:
        return Envelope(data=PersonDetail(
            slug=row.slug, name=row.name, discord_username=row.discord_username,
            civ_slug=row.civ_slug, role_in_civ=row.role_in_civ, bio=row.bio,
        ))
    # Fall through to archive_user (Discord identity as a person) —
    # auth-gated to prevent user enumeration.
    if user is None:
        raise HTTPException(status_code=404, detail="person not found")
    row = db.execute(
        text(
            "SELECT discord_username AS slug, display_name AS name, "
            "discord_username, civ_slug, beat AS role_in_civ, bio "
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
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    if db.execute(text("SELECT 1 FROM person WHERE slug = :s"), {"s": body.slug}).first():
        raise HTTPException(status_code=409, detail=f"slug '{body.slug}' already exists")
    # FK validation: civ_slug must point at a real civilization if provided.
    if body.civ_slug:
        exists = db.execute(
            text("SELECT 1 FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
            {"s": body.civ_slug},
        ).first()
        if not exists:
            raise HTTPException(status_code=400, detail=f"civilization '{body.civ_slug}' not found")
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
    log_audit(
        db, user["id"], "person.create", "person", pid,
        metadata={"slug": body.slug},
        ip_address=request.client.host if request.client else None,
    )
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
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    row = db.execute(
        text("SELECT id FROM person WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    # exclude_unset preserves explicit-NULL writes (so the caller can
    # clear a field by sending {"bio": null}); the previous "is not
    # None" filter silently dropped them.
    fields = patch.model_dump(exclude_unset=True)
    # Treat empty string civ_slug as None (clears the link).
    if "civ_slug" in fields and fields["civ_slug"] == "":
        fields["civ_slug"] = None
    # FK check when civ_slug is being set to a non-null value.
    if fields.get("civ_slug"):
        exists = db.execute(
            text("SELECT 1 FROM civilization WHERE slug = :s AND deleted_at IS NULL"),
            {"s": fields["civ_slug"]},
        ).first()
        if not exists:
            raise HTTPException(status_code=400, detail=f"civilization '{fields['civ_slug']}' not found")
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
    changed = [k for k in fields.keys() if k != "id"]
    record_revision(db, "person", row.id, user["id"],
                    f"patched {', '.join(changed)}" if changed else "no-op patch",
                    _person_snapshot(new_row))
    log_audit(
        db, user["id"], "person.patch", "person", row.id,
        metadata={"slug": slug, "fields_changed": changed},
        ip_address=request.client.host if request.client else None,
    )
    if changed:
        notify_watchers(
            db, "person", row.id, user["id"],
            title=f"Person updated: {new_row.name}",
            body=f"Fields changed: {', '.join(changed)}",
            link=f"/profile/{new_row.slug}",
        )
    db.commit()
    return Envelope(data=PersonDetail(
        slug=new_row.slug, name=new_row.name,
        discord_username=new_row.discord_username, civ_slug=new_row.civ_slug,
        role_in_civ=new_row.role_in_civ, bio=new_row.bio,
    ))


# ---------------------------------------------------------------------
# DELETE /api/v1/people/{slug} — soft-delete (historian+ only)
# ---------------------------------------------------------------------
@router.delete("/{slug}", status_code=204)
def delete_person(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_historian_or_higher),
):
    row = db.execute(
        text("SELECT id FROM person WHERE slug = :s AND deleted_at IS NULL"),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    db.execute(
        text("UPDATE person SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": row.id},
    )
    record_revision(db, "person", row.id, user["id"], "deleted", {"slug": slug})
    log_audit(
        db, user["id"], "person.delete", "person", row.id,
        metadata={"slug": slug},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


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
