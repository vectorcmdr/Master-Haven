"""
SQLAlchemy engine + session factory for the Archive.

Why SQLAlchemy when the schema is hand-written SQL:
- We use SQLAlchemy as a connection pool, transaction manager, and
  result-row mapper. We do NOT use the ORM declarative layer.
- Route handlers should use raw SQL via session.execute(text("..."))
  or call helper functions in app/repos/ (added in Phase 2).

Per-connection setup:
- SQLite has foreign_keys=OFF by default. We turn it on for every
  connection via the `connect` event handler.
- WAL journal mode is set once on the file by the first writer; we
  also re-assert it here for clarity. Setting it per-connection is a
  no-op after the first time.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings


def _build_engine() -> Engine:
    """Build the single Engine the app uses for the lifetime of the process."""
    settings = get_settings()
    url = f"sqlite:///{settings.database_path}"
    engine = create_engine(
        url,
        # check_same_thread=False allows multiple threads to share the
        # connection pool (FastAPI dispatches per-request on a thread).
        connect_args={"check_same_thread": False},
        # Keep the pool small — SQLite is single-writer anyway.
        pool_size=5,
        max_overflow=10,
        # Recycle connections after 1h so stale handles don't hold
        # WAL pages forever.
        pool_recycle=3600,
        # echo=False — flip to True locally for verbose query logs.
        echo=False,
        future=True,
    )

    # Apply per-connection PRAGMAs every time a new connection is opened.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        # Foreign keys are essential — half the schema relies on
        # ON DELETE CASCADE.
        cursor.execute("PRAGMA foreign_keys = ON")
        # WAL gives us non-blocking reads while a write is in flight.
        cursor.execute("PRAGMA journal_mode = WAL")
        # Reasonable defaults for a single-Pi setup.
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()

    return engine


# Single global engine. Built lazily — actually built on first call to
# get_session() so importing this module is cheap.
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _ensure_factory() -> None:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _build_engine()
        _SessionLocal = sessionmaker(
            bind=_engine,
            autocommit=False,
            autoflush=False,
            future=True,
        )


def get_engine() -> Engine:
    """Return the singleton Engine (build on first call)."""
    _ensure_factory()
    assert _engine is not None
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Context manager: open a session, commit on success, rollback on error.

    Use this OUTSIDE FastAPI request handling (background jobs, scripts).
    Inside FastAPI, use `Depends(get_db)` instead so the session is
    closed when the request finishes.
    """
    _ensure_factory()
    assert _SessionLocal is not None
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Iterator[Session]:
    """
    FastAPI dependency: yields a session, closes it after the response.

    Usage in a route:

        from fastapi import Depends
        from app.db import get_db

        @router.get("/things")
        def list_things(db: Session = Depends(get_db)):
            return db.execute(text("SELECT ...")).fetchall()
    """
    _ensure_factory()
    assert _SessionLocal is not None
    s = _SessionLocal()
    try:
        yield s
    finally:
        s.close()
