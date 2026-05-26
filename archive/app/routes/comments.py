"""
Comments — on drafts (inline-quoted or document-level).

GET    /api/v1/drafts/{draft_id}/comments              list
POST   /api/v1/drafts/{draft_id}/comments              create
DELETE /api/v1/drafts/{draft_id}/comments/{comment_id} delete (author only)

Permissions:
- list / create: any team-role user (so editors can leave review
  comments without being co-authors)
- delete: only the comment's author

`quoted_text` is optional — when set, the frontend highlights that
phrase in the draft body and anchors the comment to it. When NULL,
it's a document-level comment.
"""

from __future__ import annotations

import html

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..deps import get_db, require_login, require_team_role
from ..models.schemas import (
    Author,
    CommentCreate,
    CommentDetail,
    Envelope,
    Meta,
)
from ..notifications import notify_comment_mentions

router = APIRouter(prefix="/api/v1", tags=["comments"])


def _comment_row_to_detail(row) -> CommentDetail:
    return CommentDetail(
        id=row.id,
        draft_id=row.draft_id,
        author=Author(
            id=row.author_id,
            slug=row.author_slug,
            name=row.author_name,
            avatar_letter=row.avatar_letter,
            avatar_color=row.avatar_color,
            role=row.base_role,
        ),
        body=row.body,
        quoted_text=row.quoted_text,
        created_at=row.created_at,
    )


def _ensure_draft_exists(db: Session, draft_id: int) -> dict:
    """Verify draft exists and return its row mapping. 404 if missing."""
    row = db.execute(
        text("SELECT id, status FROM draft WHERE id = :id AND deleted_at IS NULL"),
        {"id": draft_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="draft not found")
    return dict(row._mapping)


@router.get("/drafts/{draft_id}/comments", response_model=Envelope[list[CommentDetail]])
def list_comments(
    draft_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    _ensure_draft_exists(db, draft_id)
    rows = db.execute(
        text(
            "SELECT c.id, c.draft_id, c.body, c.quoted_text, c.created_at, "
            "c.author_id, u.discord_username AS author_slug, "
            "u.display_name AS author_name, u.avatar_letter, "
            "u.avatar_color, u.base_role "
            "FROM draft_comment c "
            "JOIN archive_user u ON u.id = c.author_id "
            "WHERE c.draft_id = :d AND c.deleted_at IS NULL "
            "ORDER BY c.created_at"
        ),
        {"d": draft_id},
    ).fetchall()
    return Envelope(
        data=[_comment_row_to_detail(r) for r in rows],
        meta=Meta(total=len(rows)),
    )


@router.post("/drafts/{draft_id}/comments", response_model=Envelope[CommentDetail], status_code=201)
def post_comment(
    draft_id: int,
    body: CommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    draft = _ensure_draft_exists(db, draft_id)
    if draft["status"] == "published":
        raise HTTPException(
            status_code=400,
            detail="cannot comment on a published draft",
        )
    # HTML-escape user-supplied text before storage so we can't render
    # injected markup downstream (notification titles, body previews).
    safe_body = html.escape(body.body)
    safe_quote = html.escape(body.quoted_text) if body.quoted_text else None
    result = db.execute(
        text(
            "INSERT INTO draft_comment (draft_id, author_id, body, quoted_text) "
            "VALUES (:d, :a, :b, :q)"
        ),
        {"d": draft_id, "a": user["id"], "b": safe_body, "q": safe_quote},
    )
    comment_id = result.lastrowid
    # @mentions (parses against the raw body so handles still match,
    # but notification body uses the already-escaped form).
    notify_comment_mentions(db, draft_id, comment_id, safe_body, user["id"])
    log_audit(
        db, user["id"], "comment.create", "draft_comment", comment_id,
        metadata={"draft_id": draft_id, "has_quote": bool(body.quoted_text)},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    row = db.execute(
        text(
            "SELECT c.id, c.draft_id, c.body, c.quoted_text, c.created_at, "
            "c.author_id, u.discord_username AS author_slug, "
            "u.display_name AS author_name, u.avatar_letter, "
            "u.avatar_color, u.base_role "
            "FROM draft_comment c "
            "JOIN archive_user u ON u.id = c.author_id "
            "WHERE c.id = :id"
        ),
        {"id": comment_id},
    ).first()
    return Envelope(data=_comment_row_to_detail(row))


@router.delete("/drafts/{draft_id}/comments/{comment_id}", status_code=204)
def delete_comment(
    draft_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    row = db.execute(
        text(
            "SELECT author_id FROM draft_comment "
            "WHERE id = :c AND draft_id = :d AND deleted_at IS NULL"
        ),
        {"c": comment_id, "d": draft_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="comment not found")
    if row.author_id != user["id"] and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="only the comment author or an admin can delete")
    db.execute(
        text("UPDATE draft_comment SET deleted_at = CURRENT_TIMESTAMP WHERE id = :c"),
        {"c": comment_id},
    )
    log_audit(db, user["id"], "comment.delete", "draft_comment", comment_id,
              metadata={"draft_id": draft_id})
    db.commit()
