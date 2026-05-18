"""
Search — full-text search across stories, inquisitions, civs, people.

Phase 2 adds:
  GET /api/v1/search?q=<term>
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/search", tags=["search"])
