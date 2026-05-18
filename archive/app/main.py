"""
Travelers Archive — FastAPI entrypoint.

Phase 1 surface:
- GET /health — liveness probe, returns version + env
- Every route module from app/routes/ is mounted, but most are empty
  stubs in Phase 1. They get fleshed out in Phases 2-4.

Edit-friendly notes:
- To add a new resource (e.g. "tags"), create app/routes/tags.py with
  a `router = APIRouter(prefix="/api/v1/tags", tags=["tags"])` and
  add `app.include_router(routes.tags.router)` below.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from . import __version__
from .config import get_settings
from .routes import (
    admin,
    auth,
    civilizations,
    comments,
    drafts,
    events,
    inquisitions,
    media,
    notifications,
    people,
    places,
    search,
    stories,
    timeline,
    watchlist,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("archive")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Travelers Archive",
        version=__version__,
        description=(
            "A No Man's Sky community archive: news room, civilizations "
            "encyclopedia, inquisitions, and collaborative drafting."
        ),
        # Auto-docs are nice for dev; we'll consider gating in prod later.
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    # ---- health ------------------------------------------------------
    @app.get("/health", tags=["meta"])
    def health() -> JSONResponse:
        """Liveness probe. Returns 200 once the app object is up."""
        return JSONResponse(
            {
                "status": "ok",
                "version": __version__,
                "env": settings.env,
            }
        )

    # ---- routes ------------------------------------------------------
    # Each module exposes a `router` (APIRouter). Most are stubs in
    # Phase 1 — they exist so import works and so the OpenAPI doc has
    # the right shape from day one.
    for module in (
        auth,
        admin,
        civilizations,
        comments,
        drafts,
        events,
        inquisitions,
        media,
        notifications,
        people,
        places,
        search,
        stories,
        timeline,
        watchlist,
    ):
        app.include_router(module.router)

    log.info(
        "archive %s up — env=%s db=%s media=%s",
        __version__,
        settings.env,
        settings.database_path,
        settings.media_path,
    )

    return app


app = create_app()
