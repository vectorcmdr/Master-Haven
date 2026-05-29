"""Creator Corner — public read endpoint, sheet-synced with DB overlay.

Source of truth model
---------------------
The "Sponsors & Creators" tab of the festival sheet is the *preseed* — anything
the festival organizers type there flows into the DB on the next sync. Admin
edits on /admin stick: editing a row sets `admin_edited = 1`, which freezes
that row against future sheet syncs. Admin can also add pure-DB rows
(`sheet_key` NULL) that aren't in the sheet at all.

Sheet layout per row (same A-J as schedule):
  A Day | B GMT | C EST | D PST | E AEST | F Host | G Event | H Location | (I) | J Link
Only rows where Host or Event is non-empty are real entries; the rest are
empty time-slot scaffolding.

Sync key: ``f"{day}|{gmt}|{host}"`` lowercased + stripped. Stable as long as the
festival doesn't move a creator's day+time+name simultaneously. If they do,
the old DB row stays around as a stale admin-only entry and admin can delete it.
"""

import csv
import io
import os
import re
import sqlite3
import time
import urllib.request

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db

router = APIRouter()

SHEET_ID = os.environ.get(
    "GF_CREATORS_SHEET_ID",
    os.environ.get("GF_SCHEDULE_SHEET_ID", "1-WKKWGXsoT2iP3FSyNAQ10ah3N9BeE9Irs1Sq7Tu_ac"),
)
GID = os.environ.get("GF_CREATORS_GID", "864481645")
CACHE_TTL = int(os.environ.get("GF_CREATORS_TTL", "300"))  # seconds

_cache: dict = {"at": 0.0}

_TIME_RE = re.compile(r"(\d{1,2}:\d{2}):\d{2}\s*(AM|PM)", re.IGNORECASE)


# ----------------------------------------------------------------------------
# Sheet fetch + parse
# ----------------------------------------------------------------------------

def _csv_url() -> str:
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}"


def _fetch_csv() -> str:
    req = urllib.request.Request(_csv_url(), headers={"User-Agent": "GrandFestival/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed Google host
        return resp.read().decode("utf-8", errors="replace")


def _fmt_time(value: str) -> str:
    value = (value or "").strip()
    return _TIME_RE.sub(lambda m: f"{m.group(1)} {m.group(2).upper()}", value)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _make_key(day: str, gmt: str, host: str) -> str:
    return f"{_norm(day)}|{_norm(gmt)}|{_norm(host)}"


def _parse_sheet(text: str) -> list[dict]:
    """Walk the CSV and emit one dict per real creator entry."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []

    out: list[dict] = []
    current_day = ""
    seen_keys: set[str] = set()
    for raw in rows[1:]:  # skip header
        cells = [(c or "").strip() for c in (raw + [""] * 10)[:10]]
        day, gmt, est, pst, aus, host, event, location, _i_col, link = cells

        if day:
            # "Festival Day N: ..." establishes the current day; other day-labels
            # (footer / housekeeping) reset and skip.
            if day.lower().startswith("festival day"):
                current_day = day
            else:
                current_day = ""

        if not current_day:
            continue
        if not (host or event or link):
            continue
        # Skip the column-J intro blurb in the very first row ("You are not
        # obligated to choose a time…"). That cell has a long text body and no
        # host/event — it's instructions, not a creator.
        if not host and not event and link and " " in link and len(link) > 60:
            continue

        entry = {
            "sheet_key": _make_key(current_day, gmt, host),
            "host": host,
            "event": event,
            "day": current_day,
            "gmt": _fmt_time(gmt),
            "est": _fmt_time(est),
            "pst": _fmt_time(pst),
            "aest": _fmt_time(aus),
            "location": location,
            "link": link,
        }
        # Sheet rarely has duplicates; drop them defensively.
        if entry["sheet_key"] in seen_keys:
            continue
        seen_keys.add(entry["sheet_key"])
        out.append(entry)
    return out


# ----------------------------------------------------------------------------
# Sync from sheet to DB
# ----------------------------------------------------------------------------

_SYNC_FIELDS = ("host", "event", "day", "location", "link")


def _sync_sheet_to_db(conn: sqlite3.Connection, entries: list[dict]) -> None:
    """Upsert each sheet row into ``creators``. Rows with ``admin_edited = 1``
    are left untouched. Pure-DB rows (``sheet_key`` NULL) are never touched.

    Time-of-day columns (gmt/est/pst/aest) are no longer synced — the website
    doesn't surface them. The DB columns still exist so historical values aren't
    erased; they just go stale on sheet-sourced rows from here on out.
    """
    for e in entries:
        existing = conn.execute(
            "SELECT id, admin_edited FROM creators WHERE sheet_key = ?",
            (e["sheet_key"],),
        ).fetchone()
        if existing:
            if existing["admin_edited"]:
                continue
            conn.execute(
                "UPDATE creators "
                "SET host=?, event=?, day=?, location=?, link=? "
                "WHERE id = ?",
                (*(e[f] for f in _SYNC_FIELDS), existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO creators (sheet_key, host, event, day, location, link) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (e["sheet_key"], *(e[f] for f in _SYNC_FIELDS)),
            )


def _maybe_sync(conn: sqlite3.Connection) -> tuple[bool, str | None]:
    """Sync if the cache is stale. Returns (did_sync, error). Sync failure is
    non-fatal — we just serve whatever's in the DB."""
    now = time.time()
    if (now - _cache.get("at", 0)) < CACHE_TTL:
        return False, None
    try:
        entries = _parse_sheet(_fetch_csv())
    except Exception as exc:  # noqa: BLE001 — sheet outage shouldn't break the page
        return False, str(exc)
    _sync_sheet_to_db(conn, entries)
    _cache["at"] = now
    return True, None


# ----------------------------------------------------------------------------
# Serialization + sort
# ----------------------------------------------------------------------------

_DAY_RE = re.compile(r"day\s*(\d+)", re.IGNORECASE)


def _day_sort_key(day: str) -> int:
    m = _DAY_RE.search(day or "")
    return int(m.group(1)) if m else 99


def _sort_key(row) -> tuple:
    """Sort key for a raw sqlite3.Row (has every column). Run BEFORE
    serialization — `_to_public` doesn't expose `display_order`. Time-of-day
    is no longer part of the contract, so we sort by day → display_order → host."""
    return (
        _day_sort_key(row["day"] or ""),
        int(row["display_order"] if row["display_order"] is not None else 100),
        (row["host"] or "").lower(),
    )


def _to_public(row) -> dict:
    return {
        "id": row["id"],
        "host": row["host"],
        "event": row["event"],
        "day": row["day"],
        "location": row["location"],
        "link": row["link"],
        # `from_sheet` lets the UI badge sheet-sourced vs. admin-only entries
        # if it ever wants to. Public consumers can ignore it.
        "from_sheet": row["sheet_key"] is not None,
    }


# ----------------------------------------------------------------------------
# Public endpoint
# ----------------------------------------------------------------------------

@router.get("/creators")
def get_creators(conn: sqlite3.Connection = Depends(get_db)):
    did_sync, sync_error = _maybe_sync(conn)
    rows = conn.execute(
        "SELECT * FROM creators WHERE hidden = 0"
    ).fetchall()
    items = [_to_public(r) for r in sorted(rows, key=_sort_key)]
    return {
        "creators": items,
        "synced_at": _cache.get("at") or None,
        "synced_now": did_sync,
        "sync_error": sync_error,
    }


# ----------------------------------------------------------------------------
# Admin endpoints — kept colocated to share the sheet-sync helpers above
# ----------------------------------------------------------------------------

from ..auth import require_admin  # noqa: E402 — lazy to avoid circular at import time
from ..models import CreatorCreate, CreatorPatch  # noqa: E402


def _row_to_admin(row) -> dict:
    return {
        **_to_public(row),
        "sheet_key": row["sheet_key"],
        "notes": row["notes"],
        "admin_edited": bool(row["admin_edited"]),
        "hidden": bool(row["hidden"]),
        "display_order": row["display_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_creator_or_404(conn: sqlite3.Connection, cid: int):
    row = conn.execute("SELECT * FROM creators WHERE id = ?", (cid,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Creator not found.")
    return row


def _admin_log(conn, action: str, target_id: int | None, notes: str | None = None) -> None:
    conn.execute(
        "INSERT INTO admin_log (action, target_id, target_type, notes) VALUES (?, ?, 'creator', ?)",
        (action, target_id, notes),
    )


@router.get("/admin/creators", dependencies=[Depends(require_admin)])
def admin_list_creators(conn: sqlite3.Connection = Depends(get_db)):
    did_sync, sync_error = _maybe_sync(conn)
    rows = conn.execute("SELECT * FROM creators ORDER BY id ASC").fetchall()
    items = [_row_to_admin(r) for r in sorted(rows, key=_sort_key)]
    return {
        "creators": items,
        "synced_at": _cache.get("at") or None,
        "synced_now": did_sync,
        "sync_error": sync_error,
    }


@router.post("/admin/creators", dependencies=[Depends(require_admin)])
def admin_create_creator(
    body: CreatorCreate, conn: sqlite3.Connection = Depends(get_db),
):
    payload = body.model_dump()
    payload.setdefault("notes", "")
    payload.setdefault("display_order", 100)
    cur = conn.execute(
        "INSERT INTO creators "
        "(sheet_key, host, event, day, gmt, est, pst, aest, location, link, notes, "
        " admin_edited, hidden, display_order) "
        "VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)",
        (
            payload["host"], payload.get("event", ""), payload.get("day", ""),
            payload.get("gmt", ""), payload.get("est", ""), payload.get("pst", ""),
            payload.get("aest", ""), payload.get("location", ""), payload.get("link", ""),
            payload["notes"], payload["display_order"],
        ),
    )
    new_id = cur.lastrowid
    _admin_log(conn, "created", new_id, f"creator={payload['host']!r}")
    row = _get_creator_or_404(conn, new_id)
    return _row_to_admin(row)


@router.patch("/admin/creators/{cid}", dependencies=[Depends(require_admin)])
def admin_edit_creator(
    cid: int, body: CreatorPatch, conn: sqlite3.Connection = Depends(get_db),
):
    _get_creator_or_404(conn, cid)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")

    # `link` must be empty or a real http(s) URL.
    if "link" in fields and fields["link"]:
        link = str(fields["link"]).strip()
        if not link.lower().startswith(("http://", "https://")) or len(link) > 500:
            raise HTTPException(status_code=400, detail="Link must be a full http(s) URL.")
        fields["link"] = link

    columns = [
        "host", "event", "day", "location", "link",
        "notes", "display_order", "hidden",
    ]
    sets = [f"{c} = ?" for c in columns if c in fields]
    values = [fields[c] for c in columns if c in fields]
    if not sets:
        raise HTTPException(status_code=400, detail="No editable fields to update.")
    # Any content edit freezes this row against future sheet syncs.
    content_changed = any(c in fields for c in columns if c not in ("hidden", "display_order"))
    if content_changed:
        sets.append("admin_edited = 1")

    values.append(cid)
    conn.execute(f"UPDATE creators SET {', '.join(sets)} WHERE id = ?", values)
    _admin_log(conn, "edited", cid, ", ".join(f"{c}={fields[c]!r}" for c in columns if c in fields))
    return _row_to_admin(_get_creator_or_404(conn, cid))


@router.post("/admin/creators/{cid}/restore", dependencies=[Depends(require_admin)])
def admin_restore_creator(cid: int, conn: sqlite3.Connection = Depends(get_db)):
    """Drop the admin override on a sheet-sourced row, letting the next sync
    pull the sheet values back. No-op for pure-admin rows (deletes them)."""
    row = _get_creator_or_404(conn, cid)
    if row["sheet_key"] is None:
        # Pure-admin row — restoring it from the sheet is meaningless; delete it.
        conn.execute("DELETE FROM creators WHERE id = ?", (cid,))
        _admin_log(conn, "deleted", cid, f"creator={row['host']!r} (pure-admin restored = deleted)")
        return {"ok": True, "deleted": True}
    # Sheet-sourced — clear admin_edited so the next sync overwrites.
    conn.execute(
        "UPDATE creators SET admin_edited = 0, hidden = 0 WHERE id = ?", (cid,)
    )
    # Force a re-sync on the next public request by busting the TTL cache.
    _cache["at"] = 0.0
    _admin_log(conn, "edited", cid, "restored to sheet values")
    return {"ok": True, "deleted": False}


@router.delete("/admin/creators/{cid}", dependencies=[Depends(require_admin)])
def admin_delete_creator(cid: int, conn: sqlite3.Connection = Depends(get_db)):
    row = _get_creator_or_404(conn, cid)
    conn.execute("DELETE FROM creators WHERE id = ?", (cid,))
    _admin_log(conn, "deleted", cid, f"creator={row['host']!r}")
    # If the row had a sheet_key, the next sync will re-create it from the
    # sheet — that's the intended escape hatch. Admin hides via `hidden`
    # instead if they want it gone permanently.
    return {"ok": True}
