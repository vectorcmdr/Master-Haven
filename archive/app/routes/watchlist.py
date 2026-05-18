"""
Watchlist — user follow list for entities and inquisitions.

GET    /api/v1/watchlist                list current user's watched items
POST   /api/v1/watchlist                add ({target_type, target_id})
DELETE /api/v1/watchlist/{id}           remove

target_type is one of: civilization, person, event, place, inquisition, user.
target_id is the integer PK of that resource.

The notification side (watchlist_update) gets wired in Phase 7 when
there's a real signal to fire on (entity edits beyond the noisy
self-edits). For now, watchlist rows just exist for the frontend to
toggle and display.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db, require_login
from ..models.schemas import Envelope, Meta, WatchlistAdd, WatchlistItem

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


@router.get("", response_model=Envelope[list[WatchlistItem]])
def list_watchlist(
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    rows = db.execute(
        text(
            "SELECT id, target_type, target_id, created_at "
            "FROM watchlist WHERE user_id = :uid ORDER BY created_at DESC"
        ),
        {"uid": user["id"]},
    ).fetchall()
    return Envelope(
        data=[
            WatchlistItem(
                id=r.id, target_type=r.target_type,
                target_id=r.target_id, created_at=r.created_at,
            )
            for r in rows
        ],
        meta=Meta(total=len(rows)),
    )


@router.post("", response_model=Envelope[WatchlistItem], status_code=201)
def add_watch(
    body: WatchlistAdd,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    # Idempotent: if it's already there, return the existing row.
    existing = db.execute(
        text(
            "SELECT id, target_type, target_id, created_at FROM watchlist "
            "WHERE user_id = :uid AND target_type = :tt AND target_id = :tid"
        ),
        {"uid": user["id"], "tt": body.target_type, "tid": body.target_id},
    ).first()
    if existing:
        return Envelope(data=WatchlistItem(
            id=existing.id, target_type=existing.target_type,
            target_id=existing.target_id, created_at=existing.created_at,
        ))
    result = db.execute(
        text(
            "INSERT INTO watchlist (user_id, target_type, target_id) "
            "VALUES (:uid, :tt, :tid)"
        ),
        {"uid": user["id"], "tt": body.target_type, "tid": body.target_id},
    )
    db.commit()
    new_id = result.lastrowid
    row = db.execute(
        text("SELECT id, target_type, target_id, created_at FROM watchlist WHERE id = :id"),
        {"id": new_id},
    ).first()
    return Envelope(data=WatchlistItem(
        id=row.id, target_type=row.target_type,
        target_id=row.target_id, created_at=row.created_at,
    ))


@router.delete("/{watch_id}", status_code=204)
def remove_watch(
    watch_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_login),
):
    result = db.execute(
        text("DELETE FROM watchlist WHERE id = :id AND user_id = :uid"),
        {"id": watch_id, "uid": user["id"]},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="watch not found")
    db.commit()
