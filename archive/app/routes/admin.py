"""
Admin — super-admin-only operational endpoints.

Phase 4 onward: user role management, Discord sync log inspection,
audit log read, etc. All endpoints require require_admin().
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
