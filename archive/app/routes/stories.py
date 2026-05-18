"""
Stories — briefs and features.

Phase 2 adds:
  GET /api/v1/stories          filter by beat/civ/doctype
  GET /api/v1/stories/{id}
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/stories", tags=["stories"])
