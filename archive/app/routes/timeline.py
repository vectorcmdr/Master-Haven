"""
Timeline — master timeline endpoint.

Phase 2 adds:
  GET /api/v1/timeline   merged events + story dates + inquisition starts
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/timeline", tags=["timeline"])
