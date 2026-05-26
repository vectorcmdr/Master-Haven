"""
Drafts — work-in-progress stories and inquisitions.

Endpoints (11; comments live in routes/comments.py):
  GET    /api/v1/drafts?view=personal|team         list
  POST   /api/v1/drafts                            create
  GET    /api/v1/drafts/{id}                       detail
  PATCH  /api/v1/drafts/{id}                       auto-save
  DELETE /api/v1/drafts/{id}                       soft delete
  POST   /api/v1/drafts/{id}/submit                draft -> in_review
  POST   /api/v1/drafts/{id}/return                in_review -> returned (editor)
  POST   /api/v1/drafts/{id}/mark_ready            in_review -> ready (editor)
  POST   /api/v1/drafts/{id}/publish               creates story OR inquisition
  POST   /api/v1/drafts/{id}/coauthors             add co-author
  DELETE /api/v1/drafts/{id}/coauthors/{user_id}   remove co-author

State machine:
   draft  --submit-->  in_review  --return->     returned
                                  --mark_ready-> ready  --publish--> published
   returned --submit--> in_review (re-submission)

Permissions:
- create: any team-role user (require_team_role)
- read: any team-role user
- patch / delete / coauthors / submit / publish: author or co-author
  only (require_can_edit_draft)
- return / mark_ready: editor (require_editor)
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import (
    get_db,
    require_can_edit_draft,
    require_editor,
    require_login,
    require_team_role,
)
from ..models.schemas import (
    Author,
    CoauthorAdd,
    DraftCoauthor,
    DraftCreate,
    DraftDetail,
    DraftPatch,
    DraftSummary,
    Envelope,
    Meta,
)
from ..notifications import (
    notify_coauthor_added,
    notify_draft_marked_ready,
    notify_draft_returned,
    notify_draft_submitted,
)

log = logging.getLogger("archive.drafts")

router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"])


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------
def _slugify(s: str) -> str:
    """Cheap slug: lowercase, strip non-alnum, collapse dashes.
    Returns 'untitled' for empty / whitespace-only / unsluggable input.
    """
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:60] if s else "") or "untitled"


def _unique_story_slug(db: Session, base_slug: str) -> str:
    """Race-safe slug picker for the story table.

    Wrapping the INSERT in `INSERT ... ON CONFLICT` would also work,
    but story has dozens of columns — keeping the loop here lets the
    caller produce a deterministic slug ahead of the INSERT. We retry
    up to 50 candidates; INSERT will UNIQUE-violate if two requests
    pick the same slug at the same millisecond, but that's much rarer
    than the previous always-pick-the-same-base behavior.
    """
    slug = base_slug
    i = 1
    while db.execute(text("SELECT 1 FROM story WHERE slug = :s"), {"s": slug}).first():
        i += 1
        slug = f"{base_slug}-{i}"
        if i > 50:
            break
    return slug


def _unique_inquisition_slug(db: Session, base_slug: str) -> str:
    """Race-safe slug picker for the inquisition table."""
    slug = base_slug
    i = 1
    while db.execute(text("SELECT 1 FROM inquisition WHERE slug = :s"), {"s": slug}).first():
        i += 1
        slug = f"{base_slug}-{i}"
        if i > 50:
            break
    return slug


def _fetch_author(db: Session, user_id: int) -> Optional[Author]:
    r = db.execute(
        text(
            "SELECT id, discord_username AS slug, display_name AS name, "
            "avatar_letter, avatar_color, base_role "
            "FROM archive_user WHERE id = :id"
        ),
        {"id": user_id},
    ).first()
    if not r:
        return None
    return Author(
        id=r.id, slug=r.slug, name=r.name,
        avatar_letter=r.avatar_letter, avatar_color=r.avatar_color,
        role=r.base_role,
    )


def _fetch_coauthors(db: Session, draft_id: int) -> list[DraftCoauthor]:
    rows = db.execute(
        text(
            "SELECT u.id, u.discord_username AS slug, u.display_name AS name, "
            "u.avatar_letter, u.avatar_color "
            "FROM draft_coauthor dc "
            "JOIN archive_user u ON u.id = dc.user_id "
            "WHERE dc.draft_id = :d "
            "ORDER BY dc.added_at"
        ),
        {"d": draft_id},
    ).fetchall()
    return [
        DraftCoauthor(
            user_id=r.id, slug=r.slug, name=r.name,
            avatar_letter=r.avatar_letter, avatar_color=r.avatar_color,
        )
        for r in rows
    ]


def _fetch_civs(db: Session, draft_id: int) -> list[str]:
    rows = db.execute(
        text("SELECT civ_slug FROM draft_civilization WHERE draft_id = :d"),
        {"d": draft_id},
    ).fetchall()
    return [r.civ_slug for r in rows]


def _draft_summary(db: Session, row) -> DraftSummary:
    author = _fetch_author(db, row.author_id)
    return DraftSummary(
        id=row.id,
        doctype=row.doctype,
        headline=row.headline,
        deck=row.deck,
        beat=row.beat,
        numeral=row.numeral,
        status=row.status,
        author=author,
        coauthors=_fetch_coauthors(db, row.id),
        civs=_fetch_civs(db, row.id),
        last_edited_at=row.last_edited_at,
        created_at=row.created_at,
        reviewed_by_id=row.reviewed_by_id,
        reviewed_at=row.reviewed_at,
    )


def _draft_detail(db: Session, row) -> DraftDetail:
    summary = _draft_summary(db, row)
    return DraftDetail(
        **summary.model_dump(),
        body=row.body or "",
        published_as_story_id=row.published_as_story_id,
        published_as_inquisition_id=row.published_as_inquisition_id,
    )


def _next_roman_numeral(db: Session) -> str:
    """
    Assign the next inquisition numeral by counting only PUBLISHED
    inquisitions (not drafts).

    Includes UNIQUE-collision retry: if `inquisition.numeral` already
    has the candidate value (race with another publisher), advance by
    one until we find a free slot.
    """
    base = (db.execute(text("SELECT COUNT(*) FROM inquisition")).scalar() or 0) + 1
    for offset in range(0, 50):
        candidate = _to_roman(base + offset)
        existing = db.execute(
            text("SELECT 1 FROM inquisition WHERE numeral = :n"),
            {"n": candidate},
        ).first()
        if not existing:
            return candidate
    # If we somehow can't find a free slot in 50 tries, fall through to
    # a high one — caller will see the UNIQUE violation and the client
    # can retry.
    return _to_roman(base + 50)


def _to_roman(n: int) -> str:
    pairs = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    out = []
    for value, sym in pairs:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


# ---------------------------------------------------------------------
# GET /api/v1/drafts
# ---------------------------------------------------------------------
@router.get("", response_model=Envelope[list[DraftSummary]])
def list_drafts(
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
    view: str = Query("personal", pattern="^(personal|team)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """
    'personal' = drafts where current user is author OR co-author.
    'team' = every non-deleted, non-published draft (visible to all
    team-role members).
    """
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if view == "personal":
        params["uid"] = user["id"]
        where = (
            "WHERE d.deleted_at IS NULL "
            "AND d.status != 'published' "
            "AND (d.author_id = :uid OR EXISTS "
            "  (SELECT 1 FROM draft_coauthor dc "
            "   WHERE dc.draft_id = d.id AND dc.user_id = :uid))"
        )
    else:  # team
        where = "WHERE d.deleted_at IS NULL AND d.status != 'published'"

    total = db.execute(
        text(f"SELECT COUNT(*) FROM draft d {where}"), params
    ).scalar() or 0

    rows = db.execute(
        text(
            f"SELECT d.id, d.doctype, d.headline, d.deck, d.body, d.beat, "
            f"d.numeral, d.status, d.author_id, d.reviewed_by_id, "
            f"d.reviewed_at, d.published_as_story_id, "
            f"d.published_as_inquisition_id, d.last_edited_at, d.created_at "
            f"FROM draft d {where} "
            f"ORDER BY d.last_edited_at DESC "
            f"LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()

    summaries = [_draft_summary(db, r) for r in rows]
    return Envelope(
        data=summaries,
        meta=Meta(page=page, page_size=page_size, total=total, extra={"view": view}),
    )


# ---------------------------------------------------------------------
# POST /api/v1/drafts
# ---------------------------------------------------------------------
@router.post("", response_model=Envelope[DraftDetail], status_code=201)
def create_draft(
    body: DraftCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    # Historian-only for inquisitions
    if body.doctype == "inquisition" and user["base_role"] != "historian" and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="only historians can start an inquisition")

    numeral = body.numeral
    if body.doctype == "inquisition" and not numeral:
        numeral = _next_roman_numeral(db)

    result = db.execute(
        text(
            "INSERT INTO draft (doctype, headline, deck, body, beat, "
            "numeral, status, author_id) "
            "VALUES (:doctype, :headline, :deck, :body, :beat, "
            ":numeral, 'draft', :author_id)"
        ),
        {
            "doctype": body.doctype,
            "headline": body.headline,
            "deck": body.deck,
            "body": body.body or "",
            "beat": body.beat,
            "numeral": numeral,
            "author_id": user["id"],
        },
    )
    draft_id = result.lastrowid
    for civ_slug in body.civs:
        db.execute(
            text("INSERT OR IGNORE INTO draft_civilization (draft_id, civ_slug) VALUES (:d, :c)"),
            {"d": draft_id, "c": civ_slug},
        )
    log_audit(db, user["id"], "draft.create", "draft", draft_id,
              metadata={"doctype": body.doctype, "numeral": numeral})
    db.commit()

    row = db.execute(
        text(
            "SELECT id, doctype, headline, deck, body, beat, numeral, status, "
            "author_id, reviewed_by_id, reviewed_at, "
            "published_as_story_id, published_as_inquisition_id, "
            "last_edited_at, created_at FROM draft WHERE id = :id"
        ),
        {"id": draft_id},
    ).first()
    return Envelope(data=_draft_detail(db, row))


# ---------------------------------------------------------------------
# GET /api/v1/drafts/{id}
# ---------------------------------------------------------------------
@router.get("/{draft_id}", response_model=Envelope[DraftDetail])
def get_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    row = db.execute(
        text(
            "SELECT id, doctype, headline, deck, body, beat, numeral, status, "
            "author_id, reviewed_by_id, reviewed_at, "
            "published_as_story_id, published_as_inquisition_id, "
            "last_edited_at, created_at FROM draft "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": draft_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="draft not found")
    return Envelope(data=_draft_detail(db, row))


# ---------------------------------------------------------------------
# PATCH /api/v1/drafts/{id}  — auto-save
# ---------------------------------------------------------------------
@router.patch("/{draft_id}", response_model=Envelope[DraftDetail])
def patch_draft(
    draft_id: int,
    patch: DraftPatch,
    db: Session = Depends(get_db),
    draft: dict = Depends(require_can_edit_draft),
):
    """Partial update. `civs` replaces the whole join (list semantics).
    Drafts can only be edited in 'draft' or 'returned' status — once
    submitted for review or marked ready, the author must return-resubmit
    via the editor flow.
    """
    if draft["status"] == "published":
        raise HTTPException(status_code=400, detail="cannot edit a published draft")
    if draft["status"] in ("in_review", "ready"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"cannot edit a draft in status={draft['status']} — "
                "ask an editor to return it first"
            ),
        )

    patch_data = patch.model_dump(exclude_unset=True)
    fields: dict = {}
    for k in ("headline", "deck", "body", "beat"):
        if k in patch_data:
            fields[k] = patch_data[k]

    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = draft_id
        db.execute(
            text(f"UPDATE draft SET {sets}, last_edited_at = CURRENT_TIMESTAMP WHERE id = :id"),
            fields,
        )
    else:
        # Always bump last_edited_at on any PATCH (auto-save heartbeat)
        db.execute(
            text("UPDATE draft SET last_edited_at = CURRENT_TIMESTAMP WHERE id = :id"),
            {"id": draft_id},
        )

    if "civs" in patch_data:
        # Explicit-NULL/empty-list semantics: setting civs to [] clears
        # all linked civs; setting it to a list replaces the whole join.
        civs = patch_data["civs"] or []
        db.execute(text("DELETE FROM draft_civilization WHERE draft_id = :d"), {"d": draft_id})
        for civ_slug in civs:
            db.execute(
                text("INSERT OR IGNORE INTO draft_civilization (draft_id, civ_slug) VALUES (:d, :c)"),
                {"d": draft_id, "c": civ_slug},
            )
    db.commit()

    row = db.execute(
        text(
            "SELECT id, doctype, headline, deck, body, beat, numeral, status, "
            "author_id, reviewed_by_id, reviewed_at, "
            "published_as_story_id, published_as_inquisition_id, "
            "last_edited_at, created_at FROM draft WHERE id = :id"
        ),
        {"id": draft_id},
    ).first()
    return Envelope(data=_draft_detail(db, row))


# ---------------------------------------------------------------------
# DELETE /api/v1/drafts/{id}  — soft delete
# ---------------------------------------------------------------------
@router.delete("/{draft_id}", status_code=204)
def delete_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    draft: dict = Depends(require_can_edit_draft),
    user: dict = Depends(require_login),
):
    db.execute(
        text("UPDATE draft SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"),
        {"id": draft_id},
    )
    log_audit(db, user["id"], "draft.delete", "draft", draft_id)
    db.commit()


# ---------------------------------------------------------------------
# POST /api/v1/drafts/{id}/submit
# ---------------------------------------------------------------------
@router.post("/{draft_id}/submit", response_model=Envelope[DraftDetail])
def submit_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    draft: dict = Depends(require_can_edit_draft),
):
    if draft["status"] not in ("draft", "returned"):
        raise HTTPException(status_code=400, detail=f"can't submit from status={draft['status']}")
    # Clear any prior reviewer attribution so a re-submission doesn't
    # appear to already have been reviewed.
    db.execute(
        text(
            "UPDATE draft SET status = 'in_review', "
            "reviewed_by_id = NULL, reviewed_at = NULL, "
            "last_edited_at = CURRENT_TIMESTAMP "
            "WHERE id = :id"
        ),
        {"id": draft_id},
    )
    log_audit(db, draft["author_id"], "draft.submit", "draft", draft_id)
    notify_draft_submitted(db, draft_id, draft["author_id"], draft.get("headline"))
    db.commit()

    row = db.execute(
        text(
            "SELECT id, doctype, headline, deck, body, beat, numeral, status, "
            "author_id, reviewed_by_id, reviewed_at, "
            "published_as_story_id, published_as_inquisition_id, "
            "last_edited_at, created_at FROM draft WHERE id = :id"
        ),
        {"id": draft_id},
    ).first()
    return Envelope(data=_draft_detail(db, row))


# ---------------------------------------------------------------------
# POST /api/v1/drafts/{id}/return  — editor only
# ---------------------------------------------------------------------
@router.post("/{draft_id}/return", response_model=Envelope[DraftDetail])
def return_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
):
    row = db.execute(
        text(
            "SELECT id, doctype, headline, status, author_id "
            "FROM draft WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": draft_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="draft not found")
    if row.status != "in_review":
        raise HTTPException(status_code=400, detail=f"can't return from status={row.status}")
    db.execute(
        text(
            "UPDATE draft SET status = 'returned', "
            "reviewed_by_id = :rev, reviewed_at = CURRENT_TIMESTAMP, "
            "last_edited_at = CURRENT_TIMESTAMP "
            "WHERE id = :id"
        ),
        {"id": draft_id, "rev": user["id"]},
    )
    log_audit(db, user["id"], "draft.return", "draft", draft_id)
    notify_draft_returned(db, draft_id, row.author_id, user["id"], row.headline)
    db.commit()

    row2 = db.execute(
        text(
            "SELECT id, doctype, headline, deck, body, beat, numeral, status, "
            "author_id, reviewed_by_id, reviewed_at, "
            "published_as_story_id, published_as_inquisition_id, "
            "last_edited_at, created_at FROM draft WHERE id = :id"
        ),
        {"id": draft_id},
    ).first()
    return Envelope(data=_draft_detail(db, row2))


# ---------------------------------------------------------------------
# POST /api/v1/drafts/{id}/mark_ready  — editor only
# ---------------------------------------------------------------------
@router.post("/{draft_id}/mark_ready", response_model=Envelope[DraftDetail])
def mark_ready(
    draft_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
):
    row = db.execute(
        text("SELECT id, headline, status, author_id FROM draft WHERE id = :id AND deleted_at IS NULL"),
        {"id": draft_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="draft not found")
    if row.status != "in_review":
        raise HTTPException(status_code=400, detail=f"can't mark_ready from status={row.status}")
    db.execute(
        text(
            "UPDATE draft SET status = 'ready', "
            "reviewed_by_id = :rev, reviewed_at = CURRENT_TIMESTAMP, "
            "last_edited_at = CURRENT_TIMESTAMP "
            "WHERE id = :id"
        ),
        {"id": draft_id, "rev": user["id"]},
    )
    log_audit(db, user["id"], "draft.mark_ready", "draft", draft_id)
    notify_draft_marked_ready(db, draft_id, row.author_id, user["id"], row.headline)
    db.commit()

    row2 = db.execute(
        text(
            "SELECT id, doctype, headline, deck, body, beat, numeral, status, "
            "author_id, reviewed_by_id, reviewed_at, "
            "published_as_story_id, published_as_inquisition_id, "
            "last_edited_at, created_at FROM draft WHERE id = :id"
        ),
        {"id": draft_id},
    ).first()
    return Envelope(data=_draft_detail(db, row2))


# ---------------------------------------------------------------------
# POST /api/v1/drafts/{id}/publish
# ---------------------------------------------------------------------
@router.post("/{draft_id}/publish", response_model=Envelope[DraftDetail])
def publish_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    draft: dict = Depends(require_can_edit_draft),
):
    """Author or co-author publishes once status='ready'."""
    if draft["status"] != "ready":
        raise HTTPException(status_code=400, detail=f"can't publish from status={draft['status']}")
    if not draft["headline"]:
        raise HTTPException(status_code=400, detail="headline required to publish")

    headline = draft["headline"]
    doctype = draft["doctype"]
    civs = _fetch_civs(db, draft_id)

    if doctype in ("brief", "feature"):
        # Compute read_minutes for features (~200 wpm)
        word_count = len((draft["body"] or "").split())
        read_minutes = max(3, word_count // 200) if doctype == "feature" else None
        # Race-safe slug picker (subject to UNIQUE check on INSERT if a
        # collision happens between SELECT and INSERT — rare).
        base_slug = _slugify(headline)
        slug = _unique_story_slug(db, base_slug)
        result = db.execute(
            text(
                "INSERT INTO story (slug, doctype, headline, deck, body, beat, "
                "author_id, published_at, read_minutes) "
                "VALUES (:slug, :doctype, :headline, :deck, :body, :beat, "
                ":author_id, CURRENT_TIMESTAMP, :read_minutes)"
            ),
            {
                "slug": slug,
                "doctype": doctype,
                "headline": headline,
                "deck": draft["deck"],
                "body": draft["body"] or "",
                "beat": draft["beat"],
                "author_id": draft["author_id"],
                "read_minutes": read_minutes,
            },
        )
        story_id = result.lastrowid
        for cs in civs:
            db.execute(
                text("INSERT OR IGNORE INTO story_civilization (story_id, civ_slug) VALUES (:s, :c)"),
                {"s": story_id, "c": cs},
            )
        db.execute(
            text(
                "UPDATE draft SET status = 'published', "
                "published_as_story_id = :sid, last_edited_at = CURRENT_TIMESTAMP "
                "WHERE id = :id"
            ),
            {"sid": story_id, "id": draft_id},
        )
        log_audit(db, draft["author_id"], "draft.publish", "draft", draft_id,
                  metadata={"published_as": "story", "story_id": story_id, "slug": slug})
    else:  # inquisition
        # Re-derive numeral at publish time so the count reflects actual
        # PUBLISHED inquisitions (not pending/abandoned drafts).
        numeral = _next_roman_numeral(db)
        base_slug = _slugify(f"inq-{numeral}")
        slug = _unique_inquisition_slug(db, base_slug)
        result = db.execute(
            text(
                "INSERT INTO inquisition (slug, numeral, title, subtitle, deck, "
                "body, state, progress, sources_count, started_at, lead_author_id) "
                "VALUES (:slug, :numeral, :title, :subtitle, :deck, :body, "
                "'in_progress', 0, 0, CURRENT_TIMESTAMP, :lead)"
            ),
            {
                "slug": slug,
                "numeral": numeral,
                "title": headline,
                "subtitle": None,
                "deck": draft["deck"],
                "body": draft["body"] or "",
                "lead": draft["author_id"],
            },
        )
        inq_id = result.lastrowid
        # Lead author + all co-authors become inquisition authors
        db.execute(
            text("INSERT OR IGNORE INTO inquisition_author (inquisition_id, user_id) VALUES (:i, :u)"),
            {"i": inq_id, "u": draft["author_id"]},
        )
        co_rows = db.execute(
            text("SELECT user_id FROM draft_coauthor WHERE draft_id = :d"),
            {"d": draft_id},
        ).fetchall()
        for r in co_rows:
            db.execute(
                text("INSERT OR IGNORE INTO inquisition_author (inquisition_id, user_id) VALUES (:i, :u)"),
                {"i": inq_id, "u": r.user_id},
            )
        for cs in civs:
            db.execute(
                text("INSERT OR IGNORE INTO inquisition_civilization (inquisition_id, civ_slug) VALUES (:i, :c)"),
                {"i": inq_id, "c": cs},
            )
        db.execute(
            text(
                "UPDATE draft SET status = 'published', "
                "published_as_inquisition_id = :iid, last_edited_at = CURRENT_TIMESTAMP "
                "WHERE id = :id"
            ),
            {"iid": inq_id, "id": draft_id},
        )
        log_audit(db, draft["author_id"], "draft.publish", "draft", draft_id,
                  metadata={"published_as": "inquisition", "inquisition_id": inq_id,
                            "numeral": numeral, "slug": slug})
    db.commit()

    row = db.execute(
        text(
            "SELECT id, doctype, headline, deck, body, beat, numeral, status, "
            "author_id, reviewed_by_id, reviewed_at, "
            "published_as_story_id, published_as_inquisition_id, "
            "last_edited_at, created_at FROM draft WHERE id = :id"
        ),
        {"id": draft_id},
    ).first()
    return Envelope(data=_draft_detail(db, row))


# ---------------------------------------------------------------------
# POST /api/v1/drafts/{id}/coauthors  — add
# ---------------------------------------------------------------------
@router.post("/{draft_id}/coauthors", status_code=201)
def add_coauthor(
    draft_id: int,
    body: CoauthorAdd,
    db: Session = Depends(get_db),
    draft: dict = Depends(require_can_edit_draft),
    user: dict = Depends(require_login),
):
    if body.user_id == draft["author_id"]:
        raise HTTPException(status_code=400, detail="author is already on the draft")
    # User must exist
    target = db.execute(
        text("SELECT id FROM archive_user WHERE id = :id AND deleted_at IS NULL"),
        {"id": body.user_id},
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    db.execute(
        text(
            "INSERT OR IGNORE INTO draft_coauthor (draft_id, user_id, added_by_id) "
            "VALUES (:d, :u, :ab)"
        ),
        {"d": draft_id, "u": body.user_id, "ab": user["id"]},
    )
    notify_coauthor_added(db, draft_id, body.user_id, user["id"], draft.get("headline"))
    log_audit(db, user["id"], "draft.coauthor_add", "draft", draft_id,
              metadata={"added_user_id": body.user_id})
    db.commit()
    return {"data": {"added": body.user_id}, "meta": {}}


# ---------------------------------------------------------------------
# DELETE /api/v1/drafts/{id}/coauthors/{user_id}  — remove
# ---------------------------------------------------------------------
@router.delete("/{draft_id}/coauthors/{user_id}", status_code=204)
def remove_coauthor(
    draft_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    draft: dict = Depends(require_can_edit_draft),
    user: dict = Depends(require_login),
):
    db.execute(
        text("DELETE FROM draft_coauthor WHERE draft_id = :d AND user_id = :u"),
        {"d": draft_id, "u": user_id},
    )
    log_audit(db, user["id"], "draft.coauthor_remove", "draft", draft_id,
              metadata={"removed_user_id": user_id})
    db.commit()
