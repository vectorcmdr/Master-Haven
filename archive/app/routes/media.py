"""
Media — uploads + serving.

POST /api/v1/media        upload (multipart, team-role+ only)
GET  /api/v1/media/{id}   metadata (rarely useful; serving happens via /media/*)

The static file mount lives in main.py (/media/{filename}).
"""

from __future__ import annotations

import logging
import mimetypes
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..audit import log_audit
from ..config import get_settings
from ..deps import get_db, require_team_role
from ..models.schemas import Envelope, MediaUploadResponse

log = logging.getLogger("archive.media")

router = APIRouter(prefix="/api/v1/media", tags=["media"])


_ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml",
}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _safe_extension(filename: str, mime_type: str) -> str:
    """Determine a safe extension from filename or fall back to mime guess."""
    suffix = Path(filename).suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
        return suffix if suffix != ".jpeg" else ".jpg"
    ext = mimetypes.guess_extension(mime_type) or ""
    return ext.lower() if ext else ".bin"


@router.post("", response_model=Envelope[MediaUploadResponse], status_code=201)
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    alt_text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_team_role),
):
    """Upload a media file. Stored under /data/media on the host volume."""
    settings = get_settings()
    media_root = Path(settings.media_path)
    media_root.mkdir(parents=True, exist_ok=True)

    # Validate MIME
    mime_type = (file.content_type or "").lower()
    if mime_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported file type '{mime_type}'. Allowed: {sorted(_ALLOWED_MIME)}",
        )

    # Read with a size guard so a giant upload can't OOM the box.
    chunks = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_BYTES:
            raise HTTPException(status_code=400, detail=f"file exceeds {_MAX_BYTES} bytes")
        chunks.append(chunk)
    data = b"".join(chunks)
    if total == 0:
        raise HTTPException(status_code=400, detail="empty file")

    # Generate a random filename to avoid path traversal / overwriting.
    ext = _safe_extension(file.filename or "upload", mime_type)
    stored_name = f"{secrets.token_urlsafe(16)}{ext}"
    storage_path = media_root / stored_name

    try:
        storage_path.write_bytes(data)
    except OSError as e:
        log.exception("media write failed: %s", e)
        raise HTTPException(status_code=500, detail="failed to save file")

    result = db.execute(
        text(
            "INSERT INTO media_asset ("
            "filename, storage_path, mime_type, size_bytes, alt_text, uploaded_by_id"
            ") VALUES (:fn, :sp, :mt, :sz, :alt, :uid)"
        ),
        {
            "fn": file.filename or stored_name,
            "sp": stored_name,
            "mt": mime_type,
            "sz": total,
            "alt": alt_text,
            "uid": user["id"],
        },
    )
    media_id = result.lastrowid
    log_audit(
        db, user["id"], "media.upload", "media_asset", media_id,
        metadata={"filename": file.filename, "size_bytes": total, "mime_type": mime_type},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    new_row = db.execute(
        text(
            "SELECT id, filename, storage_path, mime_type, size_bytes, "
            "width, height, alt_text, created_at "
            "FROM media_asset WHERE id = :id"
        ),
        {"id": media_id},
    ).first()
    return Envelope(data=MediaUploadResponse(
        id=new_row.id,
        filename=new_row.filename,
        url=f"/media/{new_row.storage_path}",
        mime_type=new_row.mime_type,
        size_bytes=new_row.size_bytes,
        width=new_row.width,
        height=new_row.height,
        alt_text=new_row.alt_text,
        created_at=new_row.created_at,
    ))


@router.get("/{media_id}", response_model=Envelope[MediaUploadResponse])
def get_media(media_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT id, filename, storage_path, mime_type, size_bytes, "
            "width, height, alt_text, created_at "
            "FROM media_asset WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": media_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="media not found")
    return Envelope(data=MediaUploadResponse(
        id=row.id,
        filename=row.filename,
        url=f"/media/{row.storage_path}",
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        width=row.width,
        height=row.height,
        alt_text=row.alt_text,
        created_at=row.created_at,
    ))
