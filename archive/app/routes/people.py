"""People — encyclopedia entries. Phase 2 adds GET; Phase 4 adds writes."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/people", tags=["people"])
