"""
Search — basic full-text across stories, inquisitions, civs, people.

GET /api/v1/search?q=<term>&limit=24

Phase 2: naive `LIKE '%q%'` search across multiple columns. Good
enough for the v0.9 mockup's expected behavior (small dataset, exact-
substring is fine). Phase 4+ can swap in SQLite FTS5 if it ever
needs to scale.

Each hit returns kind / id / slug / title / optional 120-char snippet
so the frontend can render mixed-result cards.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models.schemas import Envelope, Meta, SearchHit

router = APIRouter(prefix="/api/v1/search", tags=["search"])


def _snippet(body: str | None, q: str, width: int = 120) -> str | None:
    if not body:
        return None
    body_lower = body.lower()
    q_lower = q.lower()
    pos = body_lower.find(q_lower)
    if pos < 0:
        # Match was on title only — just return the first slice
        return body[:width].strip() + ("..." if len(body) > width else "")
    half = width // 2
    start = max(0, pos - half)
    end = min(len(body), pos + len(q) + half)
    s = body[start:end].strip()
    if start > 0:
        s = "..." + s
    if end < len(body):
        s = s + "..."
    return s


@router.get("", response_model=Envelope[list[SearchHit]])
def search(
    db: Session = Depends(get_db),
    q: str = Query(..., min_length=2, max_length=120),
    limit: int = Query(24, ge=1, le=100),
):
    """Return matching hits across all four searchable resources."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="q is required")
    pattern = f"%{q}%"
    hits: list[SearchHit] = []

    # Stories
    rows = db.execute(
        text(
            "SELECT id, slug, headline, deck, body "
            "FROM story "
            "WHERE deleted_at IS NULL "
            "AND (headline LIKE :p OR deck LIKE :p OR body LIKE :p) "
            "ORDER BY published_at DESC LIMIT :lim"
        ),
        {"p": pattern, "lim": limit},
    ).fetchall()
    for r in rows:
        hits.append(SearchHit(
            kind="story",
            id=r.id,
            slug=r.slug,
            title=r.headline,
            snippet=_snippet(r.body or r.deck, q),
        ))

    # Inquisitions
    rows = db.execute(
        text(
            "SELECT id, slug, title, deck, body "
            "FROM inquisition "
            "WHERE deleted_at IS NULL "
            "AND (title LIKE :p OR deck LIKE :p OR body LIKE :p) "
            "ORDER BY started_at DESC LIMIT :lim"
        ),
        {"p": pattern, "lim": limit},
    ).fetchall()
    for r in rows:
        hits.append(SearchHit(
            kind="inquisition",
            id=r.id,
            slug=r.slug,
            title=r.title,
            snippet=_snippet(r.body or r.deck, q),
        ))

    # Civilizations
    rows = db.execute(
        text(
            "SELECT id, slug, name, tagline, description "
            "FROM civilization "
            "WHERE deleted_at IS NULL "
            "AND (name LIKE :p OR tagline LIKE :p OR description LIKE :p) "
            "ORDER BY name LIMIT :lim"
        ),
        {"p": pattern, "lim": limit},
    ).fetchall()
    for r in rows:
        hits.append(SearchHit(
            kind="civilization",
            id=r.id,
            slug=r.slug,
            title=r.name,
            snippet=_snippet(r.description or r.tagline, q),
        ))

    # People (via archive_user — that's where personas live in Phase 2)
    rows = db.execute(
        text(
            "SELECT id, discord_username AS slug, display_name AS name, bio "
            "FROM archive_user "
            "WHERE deleted_at IS NULL "
            "AND (display_name LIKE :p OR discord_username LIKE :p OR bio LIKE :p) "
            "ORDER BY display_name LIMIT :lim"
        ),
        {"p": pattern, "lim": limit},
    ).fetchall()
    for r in rows:
        hits.append(SearchHit(
            kind="person",
            id=r.id,
            slug=r.slug,
            title=r.name,
            snippet=_snippet(r.bio, q),
        ))

    return Envelope(
        data=hits,
        meta=Meta(total=len(hits), extra={"q": q}),
    )
