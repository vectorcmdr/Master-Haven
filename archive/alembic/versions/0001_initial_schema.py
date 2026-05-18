"""initial schema (Phase 3 design, 17 tables)

Revision ID: 0001
Revises:
Create Date: 2026-05-17

Applies the hand-written schema from `sql/initial_schema.sql` verbatim.

We deliberately don't translate this to SQLAlchemy DDL — the SQL file is
the design contract. Any future schema change is a NEW revision that
ALTERs from this baseline; we don't edit this migration or the SQL file.
"""

from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _read_schema_sql() -> str:
    """
    Locate sql/initial_schema.sql relative to the repo layout.

    This file lives at archive/alembic/versions/0001_initial_schema.py,
    so the SQL file is two levels up: archive/sql/initial_schema.sql.
    """
    here = Path(__file__).resolve()
    sql_path = here.parent.parent.parent / "sql" / "initial_schema.sql"
    if not sql_path.exists():
        raise RuntimeError(
            f"Initial schema SQL not found at {sql_path}. "
            "Make sure sql/initial_schema.sql was copied into the image."
        )
    return sql_path.read_text(encoding="utf-8")


def upgrade() -> None:
    """
    Apply the full schema.

    SQLite's sqlite3.executescript() handles the multi-statement file
    in one call. We grab the raw DBAPI connection via SQLAlchemy and
    call it directly — Alembic's op.execute() doesn't handle multiple
    statements well.

    The schema's leading PRAGMA statements (foreign_keys, journal_mode)
    apply to this connection only. The app sets them again per-
    connection via app/db.py — that's intentional belt-and-suspenders.
    """
    sql = _read_schema_sql()
    bind = op.get_bind()
    raw = bind.connection.connection            # the underlying sqlite3 conn
    raw.executescript(sql)


def downgrade() -> None:
    """
    Drop every table in reverse FK order.

    We don't normally need to downgrade a baseline migration — if you
    want a fresh DB, delete archive.db. But Alembic requires the hook.
    """
    op.execute("PRAGMA foreign_keys = OFF")
    for table in [
        "audit_log",
        "source_citation",
        "source",
        "media_attachment",
        "media_asset",
        "entity_revision",
        "watchlist",
        "notification",
        "draft_comment",
        "draft_civilization",
        "draft_coauthor",
        "draft",
        "inquisition_civilization",
        "inquisition_author",
        "inquisition",
        "story_civilization",
        "story",
        "place",
        "event",
        "person",
        "civilization",
        "discord_sync_log",
        "archive_user",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("PRAGMA foreign_keys = ON")
