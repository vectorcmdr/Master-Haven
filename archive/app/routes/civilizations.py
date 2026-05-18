"""
Civilizations — encyclopedia entries.

Phase 1: stub. Phase 2 adds the read endpoints:
  GET /api/v1/civilizations
  GET /api/v1/civilizations/{slug}
  GET /api/v1/civilizations/{slug}/coverage
Phase 4 adds writes (POST/PATCH + revision history).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/civilizations", tags=["civilizations"])
