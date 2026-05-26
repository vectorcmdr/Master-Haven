"""
Stories — briefs and features.

GET /api/v1/stories                     filter by beat / civ / doctype
GET /api/v1/stories/{id}                story detail (with body)

Writes come in Phase 4 (publish flow lives on /api/v1/drafts/{id}/publish).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import get_db, require_admin, require_editor
from ..models.schemas import (
    Author,
    Envelope,
    Meta,
    StoryDetail,
    StoryPatch,
    StorySummary,
)

router = APIRouter(prefix="/api/v1/stories", tags=["stories"])


def _author_from_row(row) -> Author:
    return Author(
        id=row.author_id,
        slug=row.author_slug,
        name=row.author_name,
        avatar_letter=row.avatar_letter,
        avatar_color=row.avatar_color,
        role=row.base_role,
    )


def _story_civs(db: Session, story_id: int) -> list[str]:
    rows = db.execute(
        text("SELECT civ_slug FROM story_civilization WHERE story_id = :sid"),
        {"sid": story_id},
    ).fetchall()
    return [r.civ_slug for r in rows]


# ---------------------------------------------------------------------
# GET /api/v1/stories
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[StorySummary]])
def list_stories(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    beat: str | None = None,
    civ: str | None = None,
    doctype: str | None = Query(None, pattern="^(brief|feature)$"),
):
    """Paginated story list. Three optional filters compose with AND."""
    base_from = (
        "FROM story s "
        "LEFT JOIN archive_user u ON u.id = s.author_id "
    )
    if civ:
        base_from += "JOIN story_civilization sc ON sc.story_id = s.id "

    where = "WHERE s.deleted_at IS NULL"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if beat:
        where += " AND s.beat = :beat"
        params["beat"] = beat
    if doctype:
        where += " AND s.doctype = :doctype"
        params["doctype"] = doctype
    if civ:
        where += " AND sc.civ_slug = :civ"
        params["civ"] = civ

    total = db.execute(
        text(f"SELECT COUNT(DISTINCT s.id) {base_from} {where}"),
        params,
    ).scalar() or 0

    rows = db.execute(
        text(
            f"SELECT DISTINCT s.id, s.slug, s.doctype, s.headline, s.deck, "
            f"s.beat, s.published_at, s.read_minutes, "
            f"s.author_id, u.discord_username AS author_slug, "
            f"u.display_name AS author_name, u.avatar_letter, "
            f"u.avatar_color, u.base_role "
            f"{base_from} {where} "
            f"ORDER BY s.published_at DESC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()

    summaries = [
        StorySummary(
            id=r.id,
            slug=r.slug,
            doctype=r.doctype,
            headline=r.headline,
            deck=r.deck,
            beat=r.beat,
            civs=_story_civs(db, r.id),
            author=_author_from_row(r),
            published_at=r.published_at,
            read_minutes=r.read_minutes,
        )
        for r in rows
    ]
    return Envelope(
        data=summaries,
        meta=Meta(
            page=page,
            page_size=page_size,
            total=total,
            extra={"beat": beat, "civ": civ, "doctype": doctype},
        ),
    )


# ---------------------------------------------------------------------
# GET /api/v1/stories/by-slug/{slug}
# ---------------------------------------------------------------------
@router.get("/by-slug/{slug}", response_model=Envelope[StoryDetail])
def get_story_by_slug(slug: str, db: Session = Depends(get_db)):
    """Resolve a story by its slug. Useful for the decorative-slug URLs."""
    row = db.execute(
        text(
            "SELECT s.id, s.slug, s.doctype, s.headline, s.deck, s.body, "
            "s.beat, s.published_at, s.read_minutes, "
            "s.author_id, u.discord_username AS author_slug, "
            "u.display_name AS author_name, u.avatar_letter, "
            "u.avatar_color, u.base_role "
            "FROM story s "
            "LEFT JOIN archive_user u ON u.id = s.author_id "
            "WHERE s.slug = :s AND s.deleted_at IS NULL"
        ),
        {"s": slug},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="story not found")
    return Envelope(data=StoryDetail(
        id=row.id, slug=row.slug, doctype=row.doctype,
        headline=row.headline, deck=row.deck, body=row.body,
        beat=row.beat, civs=_story_civs(db, row.id),
        author=_author_from_row(row),
        published_at=row.published_at, read_minutes=row.read_minutes,
    ))


# ---------------------------------------------------------------------
# GET /api/v1/stories/{id}
# ---------------------------------------------------------------------
@router.get("/{story_id}", response_model=Envelope[StoryDetail])
def get_story(story_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT s.id, s.slug, s.doctype, s.headline, s.deck, s.body, "
            "s.beat, s.published_at, s.read_minutes, "
            "s.author_id, u.discord_username AS author_slug, "
            "u.display_name AS author_name, u.avatar_letter, "
            "u.avatar_color, u.base_role "
            "FROM story s "
            "LEFT JOIN archive_user u ON u.id = s.author_id "
            "WHERE s.id = :id AND s.deleted_at IS NULL"
        ),
        {"id": story_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="story not found")
    return Envelope(data=StoryDetail(
        id=row.id,
        slug=row.slug,
        doctype=row.doctype,
        headline=row.headline,
        deck=row.deck,
        body=row.body,
        beat=row.beat,
        civs=_story_civs(db, row.id),
        author=_author_from_row(row),
        published_at=row.published_at,
        read_minutes=row.read_minutes,
    ))


# ---------------------------------------------------------------------
# PATCH /api/v1/stories/{id}  — editor only
# ---------------------------------------------------------------------
@router.patch("/{story_id}", response_model=Envelope[StoryDetail])
def patch_story(
    story_id: int,
    patch: StoryPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
):
    """Edit a published story. Editor+ only (admin counts as editor)."""
    row = db.execute(
        text("SELECT id FROM story WHERE id = :id AND deleted_at IS NULL"),
        {"id": story_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="story not found")
    fields = patch.model_dump(exclude_unset=True)
    civs = fields.pop("civs", None)
    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = row.id
        db.execute(
            text(f"UPDATE story SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            fields,
        )
    if civs is not None:
        db.execute(text("DELETE FROM story_civilization WHERE story_id = :s"), {"s": story_id})
        for cs in civs:
            db.execute(
                text("INSERT OR IGNORE INTO story_civilization (story_id, civ_slug) VALUES (:s, :c)"),
                {"s": story_id, "c": cs},
            )
    log_audit(
        db, user["id"], "story.patch", "story", story_id,
        metadata={"fields_changed": [k for k in fields.keys() if k != "id"]},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    new_row = db.execute(
        text(
            "SELECT s.id, s.slug, s.doctype, s.headline, s.deck, s.body, "
            "s.beat, s.published_at, s.read_minutes, "
            "s.author_id, u.discord_username AS author_slug, "
            "u.display_name AS author_name, u.avatar_letter, "
            "u.avatar_color, u.base_role "
            "FROM story s LEFT JOIN archive_user u ON u.id = s.author_id "
            "WHERE s.id = :id"
        ),
        {"id": story_id},
    ).first()
    return Envelope(data=StoryDetail(
        id=new_row.id, slug=new_row.slug, doctype=new_row.doctype,
        headline=new_row.headline, deck=new_row.deck, body=new_row.body,
        beat=new_row.beat, civs=_story_civs(db, new_row.id),
        author=_author_from_row(new_row),
        published_at=new_row.published_at, read_minutes=new_row.read_minutes,
    ))


# ---------------------------------------------------------------------
# DELETE /api/v1/stories/{id} — soft-delete (admin only)
# ---------------------------------------------------------------------
@router.delete("/{story_id}", status_code=204)
def delete_story(
    story_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    row = db.execute(
        text("SELECT id, slug FROM story WHERE id = :id AND deleted_at IS NULL"),
        {"id": story_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="story not found")
    db.execute(
        text("UPDATE story SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": story_id},
    )
    log_audit(
        db, user["id"], "story.delete", "story", story_id,
        metadata={"slug": row.slug},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
