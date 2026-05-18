"""
Notifications — user inbox.

GET    /api/v1/notifications              list for current user
GET    /api/v1/notifications/count        unread count (light)
PATCH  /api/v1/notifications/{id}/read    mark single as read
PATCH  /api/v1/notifications/read_all     mark all unread as read

All endpoints require_login. Notifications are user-scoped — you
only see your own.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db, require_login
from ..models.schemas import Envelope, Meta, NotificationDetail

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=Envelope[list[NotificationDetail]])
def list_notifications(
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    where = "WHERE user_id = :uid"
    params: dict = {"uid": user["id"], "limit": page_size, "offset": (page - 1) * page_size}
    if unread_only:
        where += " AND is_read = 0"
    total = db.execute(
        text(f"SELECT COUNT(*) FROM notification {where}"), params
    ).scalar() or 0
    rows = db.execute(
        text(
            f"SELECT id, type, title, body, link, related_draft_id, "
            f"related_user_id, is_read, created_at "
            f"FROM notification {where} "
            f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()
    return Envelope(
        data=[
            NotificationDetail(
                id=r.id, type=r.type, title=r.title, body=r.body, link=r.link,
                related_draft_id=r.related_draft_id, related_user_id=r.related_user_id,
                is_read=bool(r.is_read), created_at=r.created_at,
            )
            for r in rows
        ],
        meta=Meta(page=page, page_size=page_size, total=total),
    )


@router.get("/count")
def unread_count(db: Session = Depends(get_db), user: dict = Depends(require_login)):
    n = db.execute(
        text("SELECT COUNT(*) FROM notification WHERE user_id = :uid AND is_read = 0"),
        {"uid": user["id"]},
    ).scalar() or 0
    return {"data": {"unread": n}, "meta": {}}


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    result = db.execute(
        text(
            "UPDATE notification SET is_read = 1 "
            "WHERE id = :id AND user_id = :uid"
        ),
        {"id": notification_id, "uid": user["id"]},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="notification not found")
    db.commit()
    return {"data": {"id": notification_id, "is_read": True}, "meta": {}}


@router.patch("/read_all")
def mark_all_read(
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    result = db.execute(
        text("UPDATE notification SET is_read = 1 WHERE user_id = :uid AND is_read = 0"),
        {"uid": user["id"]},
    )
    db.commit()
    return {"data": {"marked": result.rowcount}, "meta": {}}
