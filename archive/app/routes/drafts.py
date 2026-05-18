"""
Drafts — work-in-progress stories and inquisitions.

Phase 4 adds the full surface (create, auto-save, coauthors, submit/
return/mark_ready/publish, comments).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"])
