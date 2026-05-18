"""Events — historical events on the master timeline. Phase 2 adds GET; Phase 4 adds writes."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/events", tags=["events"])
