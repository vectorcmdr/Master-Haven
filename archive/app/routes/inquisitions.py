"""
Inquisitions — long-form historical investigations.

GET    /api/v1/inquisitions                paginated list
GET    /api/v1/inquisitions/by-slug/{slug} slug-based lookup
GET    /api/v1/inquisitions/{id}           detail with body
PATCH  /api/v1/inquisitions/{id}           lifecycle: state, progress, sources_count, etc.
DELETE /api/v1/inquisitions/{id}           soft-delete (admin only)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import get_db, require_admin, require_editor, require_login
from ..notifications import notify_watchers
from ..models.schemas import (
    Author,
    Envelope,
    InquisitionDetail,
    InquisitionPatch,
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


def _batch_authors(db: Session, inq_ids: list[int]) -> dict[int, list[Author]]:
    """Fetch authors for many inquisitions in one query (avoids N+1)."""
    if not inq_ids:
        return {}
    placeholders = ",".join(str(int(i)) for i in inq_ids)
    rows = db.execute(
        text(
            "SELECT ia.inquisition_id, u.id, u.discord_username AS slug, "
            "u.display_name AS name, u.avatar_letter, u.avatar_color, "
            "u.base_role AS role "
            f"FROM inquisition_author ia "
            f"JOIN archive_user u ON u.id = ia.user_id "
            f"WHERE ia.inquisition_id IN ({placeholders}) "
            "ORDER BY ia.added_at"
        )
    ).fetchall()
    out: dict[int, list[Author]] = defaultdict(list)
    for r in rows:
        out[r.inquisition_id].append(Author(
            id=r.id, slug=r.slug, name=r.name,
            avatar_letter=r.avatar_letter, avatar_color=r.avatar_color,
            role=r.role,
        ))
    return out


def _batch_civs(db: Session, inq_ids: list[int]) -> dict[int, list[str]]:
    """Fetch civ tags for many inquisitions in one query."""
    if not inq_ids:
        return {}
    placeholders = ",".join(str(int(i)) for i in inq_ids)
    rows = db.execute(
        text(
            f"SELECT inquisition_id, civ_slug FROM inquisition_civilization "
            f"WHERE inquisition_id IN ({placeholders})"
        )
    ).fetchall()
    out: dict[int, list[str]] = defaultdict(list)
    for r in rows:
        out[r.inquisition_id].append(r.civ_slug)
    return out


# ---------------------------------------------------------------------
# GET /api/v1/inquisitions
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[InquisitionSummary]])
def list_inquisitions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    state: Optional[str] = Query(None, pattern="^(in_progress|closed|archived)$"),
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

    ids = [r.id for r in rows]
    authors_by_id = _batch_authors(db, ids)
    civs_by_id = _batch_civs(db, ids)

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
            authors=authors_by_id.get(r.id, []),
            civs=civs_by_id.get(r.id, []),
        )
        for r in rows
    ]
    return Envelope(
        data=summaries,
        meta=Meta(page=page, page_size=page_size, total=total),
    )


# ---------------------------------------------------------------------
# GET /api/v1/inquisitions/by-slug/{slug}
# ---------------------------------------------------------------------
@router.get("/by-slug/{slug}", response_model=Envelope[InquisitionDetail])
def get_inquisition_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    truncate: bool = Query(False, description="Return only first 1000 chars of body for anonymous list views"),
):
    """Resolve an inquisition by slug. Supports optional body truncation."""
    row = db.execute(
        text(
            "SELECT id, slug, numeral, title, subtitle, deck, body, state, "
            "progress, sources_count, started_at, closed_at "
            "FROM inquisition WHERE slug = :s AND deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="inquisition not found")
    body = row.body or ""
    if truncate and len(body) > 1000:
        body = body[:1000] + "..."
    return Envelope(data=InquisitionDetail(
        id=row.id, slug=row.slug, numeral=row.numeral, title=row.title,
        subtitle=row.subtitle, deck=row.deck, body=body, state=row.state,
        progress=row.progress, sources_count=row.sources_count,
        started_at=row.started_at, closed_at=row.closed_at,
        authors=_inq_authors(db, row.id), civs=_inq_civs(db, row.id),
    ))


# ---------------------------------------------------------------------
# GET /api/v1/inquisitions/{id}
# ---------------------------------------------------------------------
@router.get("/{inq_id}", response_model=Envelope[InquisitionDetail])
def get_inquisition(
    inq_id: int,
    db: Session = Depends(get_db),
    truncate: bool = Query(False),
):
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
    body = row.body or ""
    if truncate and len(body) > 1000:
        body = body[:1000] + "..."
    return Envelope(data=InquisitionDetail(
        id=row.id,
        slug=row.slug,
        numeral=row.numeral,
        title=row.title,
        subtitle=row.subtitle,
        deck=row.deck,
        body=body,
        state=row.state,
        progress=row.progress,
        sources_count=row.sources_count,
        started_at=row.started_at,
        closed_at=row.closed_at,
        authors=_inq_authors(db, row.id),
        civs=_inq_civs(db, row.id),
    ))


# ---------------------------------------------------------------------
# PATCH /api/v1/inquisitions/{id}  — lifecycle updates (editor+ only)
# ---------------------------------------------------------------------
@router.patch("/{inq_id}", response_model=Envelope[InquisitionDetail])
def patch_inquisition(
    inq_id: int,
    patch: InquisitionPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
):
    """Update an inquisition's lifecycle fields (state/progress/sources_count/body)."""
    row = db.execute(
        text("SELECT id, state FROM inquisition WHERE id = :id AND deleted_at IS NULL"),
        {"id": inq_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="inquisition not found")
    fields = patch.model_dump(exclude_unset=True)
    # Auto-set closed_at when transitioning to 'closed'.
    if fields.get("state") == "closed" and row.state != "closed":
        fields["closed_at"] = None  # placeholder; we use CURRENT_TIMESTAMP below
        sets_parts = []
        for k in fields.keys():
            if k == "closed_at":
                sets_parts.append("closed_at = CURRENT_TIMESTAMP")
            else:
                sets_parts.append(f"{k} = :{k}")
        sets = ", ".join(sets_parts)
        fields.pop("closed_at")  # remove placeholder so it's not bound
        params = {**fields, "id": row.id}
        db.execute(
            text(f"UPDATE inquisition SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            params,
        )
    elif fields.get("state") in ("in_progress", "archived") and row.state == "closed":
        # Reopening or archiving — clear closed_at when going back to in_progress.
        if fields.get("state") == "in_progress":
            fields["closed_at"] = None
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        params = {**fields, "id": row.id}
        db.execute(
            text(f"UPDATE inquisition SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            params,
        )
    elif fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        params = {**fields, "id": row.id}
        db.execute(
            text(f"UPDATE inquisition SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            params,
        )
    log_audit(
        db, user["id"], "inquisition.patch", "inquisition", row.id,
        metadata={"fields_changed": list(fields.keys())},
        ip_address=request.client.host if request.client else None,
    )
    if fields:
        notify_watchers(
            db, "inquisition", row.id, user["id"],
            title="Inquisition updated",
            body=f"Fields changed: {', '.join(fields.keys())}",
            link=f"/inquisition/{row.id}",
        )
    db.commit()
    new_row = db.execute(
        text(
            "SELECT id, slug, numeral, title, subtitle, deck, body, state, "
            "progress, sources_count, started_at, closed_at "
            "FROM inquisition WHERE id = :id"
        ),
        {"id": row.id},
    ).first()
    return Envelope(data=InquisitionDetail(
        id=new_row.id, slug=new_row.slug, numeral=new_row.numeral,
        title=new_row.title, subtitle=new_row.subtitle, deck=new_row.deck,
        body=new_row.body, state=new_row.state, progress=new_row.progress,
        sources_count=new_row.sources_count, started_at=new_row.started_at,
        closed_at=new_row.closed_at,
        authors=_inq_authors(db, new_row.id), civs=_inq_civs(db, new_row.id),
    ))


# ---------------------------------------------------------------------
# DELETE /api/v1/inquisitions/{id}  — soft-delete (admin only)
# ---------------------------------------------------------------------
@router.delete("/{inq_id}", status_code=204)
def delete_inquisition(
    inq_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    row = db.execute(
        text("SELECT id, slug, numeral FROM inquisition WHERE id = :id AND deleted_at IS NULL"),
        {"id": inq_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="inquisition not found")
    db.execute(
        text("UPDATE inquisition SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": inq_id},
    )
    log_audit(
        db, user["id"], "inquisition.delete", "inquisition", inq_id,
        metadata={"slug": row.slug, "numeral": row.numeral},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()


# ---------------------------------------------------------------------
# POST /api/v1/inquisitions/{id}/coauthors  — add co-author
# ---------------------------------------------------------------------
@router.post("/{inq_id}/coauthors", status_code=201)
def add_inquisition_coauthor(
    inq_id: int,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    """Add a co-author to a published inquisition. Lead author or admin only."""
    inq = db.execute(
        text("SELECT id, lead_author_id FROM inquisition WHERE id = :id AND deleted_at IS NULL"),
        {"id": inq_id},
    ).first()
    if not inq:
        raise HTTPException(status_code=404, detail="inquisition not found")
    if inq.lead_author_id != user["id"] and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="only the lead author or an admin can add co-authors")
    target_id = body.get("user_id")
    if not isinstance(target_id, int):
        raise HTTPException(status_code=400, detail="user_id required")
    target = db.execute(
        text("SELECT id FROM archive_user WHERE id = :id AND deleted_at IS NULL"),
        {"id": target_id},
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    db.execute(
        text(
            "INSERT OR IGNORE INTO inquisition_author (inquisition_id, user_id) "
            "VALUES (:i, :u)"
        ),
        {"i": inq_id, "u": target_id},
    )
    log_audit(
        db, user["id"], "inquisition.coauthor_add", "inquisition", inq_id,
        metadata={"added_user_id": target_id},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"data": {"added": target_id}, "meta": {}}


# ---------------------------------------------------------------------
# DELETE /api/v1/inquisitions/{id}/coauthors/{user_id}  — remove co-author
# ---------------------------------------------------------------------
@router.delete("/{inq_id}/coauthors/{user_id}", status_code=204)
def remove_inquisition_coauthor(
    inq_id: int,
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    """Remove a co-author. Only the lead author or an admin can do this."""
    inq = db.execute(
        text("SELECT id, lead_author_id FROM inquisition WHERE id = :id AND deleted_at IS NULL"),
        {"id": inq_id},
    ).first()
    if not inq:
        raise HTTPException(status_code=404, detail="inquisition not found")
    if inq.lead_author_id != user["id"] and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="only the lead author or an admin can remove co-authors")
    if user_id == inq.lead_author_id:
        raise HTTPException(status_code=400, detail="cannot remove the lead author")
    db.execute(
        text("DELETE FROM inquisition_author WHERE inquisition_id = :i AND user_id = :u"),
        {"i": inq_id, "u": user_id},
    )
    log_audit(
        db, user["id"], "inquisition.coauthor_remove", "inquisition", inq_id,
        metadata={"removed_user_id": user_id},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
