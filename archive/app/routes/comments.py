"""Comments — on drafts (inline or document-level). Phase 4 adds endpoints; nested under /drafts/{id}/comments."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["comments"])
