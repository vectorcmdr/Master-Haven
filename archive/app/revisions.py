"""
Entity revision helper.

Every successful create/patch on civilization / person / event / place
writes a row to entity_revision with the full post-change JSON snapshot.

Snapshot format: {col_name: value, ...} as a dict, json-serialized
on insert.

NOT for stories or inquisitions — those publish-once, edit-rarely
content types don't get a wiki-style revision history per the schema
comment.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def record_revision(
    db: Session,
    entity_type: str,
    entity_id: int,
    changed_by_id: int,
    change_summary: str | None,
    snapshot: dict[str, Any],
) -> None:
    """Insert entity_revision row. Does NOT commit — caller owns txn."""
    if entity_type not in ("civilization", "person", "event", "place"):
        raise ValueError(f"unsupported entity_type: {entity_type}")
    db.execute(
        text(
            "INSERT INTO entity_revision (entity_type, entity_id, "
            "changed_by_id, change_summary, snapshot_json) "
            "VALUES (:et, :eid, :cb, :cs, :snap)"
        ),
        {
            "et": entity_type,
            "eid": entity_id,
            "cb": changed_by_id,
            "cs": change_summary,
            "snap": json.dumps(snapshot, default=str),
        },
    )
