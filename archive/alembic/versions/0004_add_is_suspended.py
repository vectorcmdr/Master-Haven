"""add is_suspended column to archive_user

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-19

Audit follow-up: the admin user editor needs a suspension toggle, but
the column didn't exist. This adds `is_suspended INTEGER NOT NULL
DEFAULT 0` so existing rows default to unsuspended.

Suspension semantics: a user with is_suspended=1 still appears in the
admin list (suspended badge), but the `_fetch_user` dependency in
deps.py treats them as logged-out (returns None). That's wired up in
the same patch as this migration.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite ALTER TABLE ADD COLUMN with NOT NULL needs a default; we use
    # 0 (= not suspended).
    op.execute(
        "ALTER TABLE archive_user "
        "ADD COLUMN is_suspended INTEGER NOT NULL DEFAULT 0 "
        "CHECK(is_suspended IN (0, 1))"
    )


def downgrade() -> None:
    # SQLite can't DROP COLUMN before 3.35; we'd need a rebuild dance.
    # Not worth the complexity — leave the column in place on downgrade.
    pass
