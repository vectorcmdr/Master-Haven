"""
Media — uploads + serving.

Phase 4 adds upload endpoint. Static serving of uploaded files is
mounted from the data volume at /media/* (configured in main.py).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/media", tags=["media"])
