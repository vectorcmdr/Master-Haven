"""sweep orphaned content (stories/inquisitions whose author was wiped)

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-18

Migration 0002 deleted demo users but didn't catch content authored
by those users that wasn't in the original demo seed list (e.g., the
Phase 4 test draft that got published as a real story).

This migration sweeps any story/inquisition whose author_id points
to a now-missing archive_user row. Also cleans up the join tables
(story_civilization, inquisition_author, inquisition_civilization)
that reference the orphaned rows.

Future-proof: if anyone hand-deletes a user later, this same cleanup
SQL is idempotent and safe to re-run via `alembic stamp head; alembic
upgrade head`.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Orphaned stories: author_id points to a missing user
    op.execute(
        "DELETE FROM story_civilization WHERE story_id IN ("
        "  SELECT s.id FROM story s "
        "  LEFT JOIN archive_user u ON u.id = s.author_id "
        "  WHERE u.id IS NULL"
        ")"
    )
    op.execute(
        "DELETE FROM story WHERE id IN ("
        "  SELECT s.id FROM story s "
        "  LEFT JOIN archive_user u ON u.id = s.author_id "
        "  WHERE u.id IS NULL"
        ")"
    )
    # Orphaned inquisitions: lead_author_id missing
    op.execute(
        "DELETE FROM inquisition_author WHERE inquisition_id IN ("
        "  SELECT i.id FROM inquisition i "
        "  LEFT JOIN archive_user u ON u.id = i.lead_author_id "
        "  WHERE u.id IS NULL"
        ")"
    )
    op.execute(
        "DELETE FROM inquisition_civilization WHERE inquisition_id IN ("
        "  SELECT i.id FROM inquisition i "
        "  LEFT JOIN archive_user u ON u.id = i.lead_author_id "
        "  WHERE u.id IS NULL"
        ")"
    )
    op.execute(
        "DELETE FROM inquisition WHERE id IN ("
        "  SELECT i.id FROM inquisition i "
        "  LEFT JOIN archive_user u ON u.id = i.lead_author_id "
        "  WHERE u.id IS NULL"
        ")"
    )
    # Orphaned draft rows (defensive — the v0.6 migration already
    # deleted demo-authored drafts, but if any slipped through)
    op.execute(
        "DELETE FROM draft_civilization WHERE draft_id IN ("
        "  SELECT d.id FROM draft d "
        "  LEFT JOIN archive_user u ON u.id = d.author_id "
        "  WHERE u.id IS NULL"
        ")"
    )
    op.execute(
        "DELETE FROM draft_coauthor WHERE draft_id IN ("
        "  SELECT d.id FROM draft d "
        "  LEFT JOIN archive_user u ON u.id = d.author_id "
        "  WHERE u.id IS NULL"
        ")"
    )
    op.execute(
        "DELETE FROM draft_comment WHERE draft_id IN ("
        "  SELECT d.id FROM draft d "
        "  LEFT JOIN archive_user u ON u.id = d.author_id "
        "  WHERE u.id IS NULL"
        ")"
    )
    op.execute(
        "DELETE FROM draft WHERE id IN ("
        "  SELECT d.id FROM draft d "
        "  LEFT JOIN archive_user u ON u.id = d.author_id "
        "  WHERE u.id IS NULL"
        ")"
    )


def downgrade() -> None:
    # Not supported — deleted orphans are gone.
    pass
