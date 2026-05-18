"""Places — galactic locations (systems, regions). Phase 2 adds GET; Phase 4 adds writes."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/places", tags=["places"])
