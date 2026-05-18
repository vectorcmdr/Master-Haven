"""Watchlist — user follow list for entities/inquisitions. Phase 4 adds endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])
