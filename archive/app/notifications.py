"""
Notification helpers.

Five trigger points across the draft system:
- notify_coauthor_added(db, draft_id, added_user_id, added_by_id)
- notify_draft_submitted(db, draft_id, author_id)     -> fan-out to editors
- notify_draft_returned(db, draft_id, author_id, reviewer_id)
- notify_draft_marked_ready(db, draft_id, author_id, reviewer_id)
- notify_comment_mentions(db, draft_id, comment_id, body, mention_author_id)

Each helper inserts notification rows but does NOT commit — caller
controls the transaction. Keeps everything atomic with the action
that triggered the notification.

Mentions: we parse `@username` patterns in the comment body and look
them up in archive_user. Unknown handles are silently skipped.
"""

from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


# @username pattern: alphanumeric + dot/underscore, 2-32 chars
_MENTION_RE = re.compile(r"@([a-z0-9_.]{2,32})", re.IGNORECASE)


def _insert_notification(
    db: Session,
    user_id: int,
    type: str,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    related_draft_id: Optional[int] = None,
    related_user_id: Optional[int] = None,
) -> None:
    db.execute(
        text(
            "INSERT INTO notification (user_id, type, title, body, link, "
            "related_draft_id, related_user_id) "
            "VALUES (:uid, :t, :title, :body, :link, :rdid, :ruid)"
        ),
        {
            "uid": user_id,
            "t": type,
            "title": title,
            "body": body,
            "link": link,
            "rdid": related_draft_id,
            "ruid": related_user_id,
        },
    )


def notify_coauthor_added(
    db: Session, draft_id: int, added_user_id: int, added_by_id: int, draft_headline: Optional[str] = None
) -> None:
    title = "You were added as a co-author"
    body = f"You can now edit \"{draft_headline}\"" if draft_headline else None
    _insert_notification(
        db,
        user_id=added_user_id,
        type="coauthor_added",
        title=title,
        body=body,
        link=f"/draft/{draft_id}",
        related_draft_id=draft_id,
        related_user_id=added_by_id,
    )


def notify_draft_submitted(
    db: Session, draft_id: int, author_id: int, draft_headline: Optional[str] = None
) -> None:
    """Fan-out to every editor (is_editor=1 OR is_admin=1)."""
    editors = db.execute(
        text(
            "SELECT id FROM archive_user "
            "WHERE deleted_at IS NULL "
            "AND (is_editor = 1 OR is_admin = 1) "
            "AND id != :author"
        ),
        {"author": author_id},
    ).fetchall()
    title = "A draft is waiting for review"
    body = f"\"{draft_headline}\" is ready" if draft_headline else None
    for r in editors:
        _insert_notification(
            db,
            user_id=r.id,
            type="draft_submitted",
            title=title,
            body=body,
            link=f"/draft/{draft_id}",
            related_draft_id=draft_id,
            related_user_id=author_id,
        )


def notify_draft_returned(
    db: Session,
    draft_id: int,
    author_id: int,
    reviewer_id: int,
    draft_headline: Optional[str] = None,
) -> None:
    title = "Your draft was returned"
    body = f"\"{draft_headline}\" has notes — see the comments" if draft_headline else "See the comments"
    _insert_notification(
        db,
        user_id=author_id,
        type="draft_returned",
        title=title,
        body=body,
        link=f"/draft/{draft_id}",
        related_draft_id=draft_id,
        related_user_id=reviewer_id,
    )


def notify_draft_marked_ready(
    db: Session,
    draft_id: int,
    author_id: int,
    reviewer_id: int,
    draft_headline: Optional[str] = None,
) -> None:
    title = "Your draft is ready to publish"
    body = f"\"{draft_headline}\" is approved" if draft_headline else None
    _insert_notification(
        db,
        user_id=author_id,
        type="draft_marked_ready",
        title=title,
        body=body,
        link=f"/draft/{draft_id}",
        related_draft_id=draft_id,
        related_user_id=reviewer_id,
    )


def notify_comment_mentions(
    db: Session,
    draft_id: int,
    comment_id: int,
    body: str,
    comment_author_id: int,
) -> int:
    """
    Parse @mentions from comment body, insert notification for each
    matched archive_user. Returns count of notifications inserted.
    """
    if not body:
        return 0
    handles = {m.group(1).lower() for m in _MENTION_RE.finditer(body)}
    if not handles:
        return 0
    inserted = 0
    for handle in handles:
        user = db.execute(
            text(
                "SELECT id, display_name FROM archive_user "
                "WHERE discord_username = :h AND deleted_at IS NULL "
                "AND id != :self"
            ),
            {"h": handle, "self": comment_author_id},
        ).first()
        if not user:
            continue
        _insert_notification(
            db,
            user_id=user.id,
            type="comment_mention",
            title="You were mentioned in a comment",
            body=body[:160],
            link=f"/draft/{draft_id}#comment-{comment_id}",
            related_draft_id=draft_id,
            related_user_id=comment_author_id,
        )
        inserted += 1
    return inserted
