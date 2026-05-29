-- Grand Festival / Summer Unification Day — SQLite schema
-- Idempotent: safe to run on every startup.

CREATE TABLE IF NOT EXISTS civilizations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    role            TEXT    NOT NULL,            -- e.g. "Pavilion District", "Festival Coordinator"
    description     TEXT    NOT NULL,
    status          TEXT    NOT NULL CHECK (status IN ('host', 'confirmed', 'tentative')),
    logo_filename   TEXT,                        -- e.g. "voyagers-haven.webp" — file lives in /uploads
    discord_link    TEXT,                        -- the civ's Discord invite/link (shown on the card)
    submitter_discord TEXT,                      -- Discord handle of person submitting
    submitter_notes TEXT,                        -- "We'd love to bring our cartographer team..."
    approval_state  TEXT NOT NULL DEFAULT 'pending'
                    CHECK (approval_state IN ('pending', 'approved', 'rejected')),
    display_order   INTEGER DEFAULT 100,         -- Admin can reorder; lower = earlier
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    approved_at     DATETIME,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_civ_approval ON civilizations(approval_state);
CREATE INDEX IF NOT EXISTS idx_civ_status   ON civilizations(status);

-- Trigger to bump updated_at on UPDATE
CREATE TRIGGER IF NOT EXISTS civ_updated_at
AFTER UPDATE ON civilizations
BEGIN
    UPDATE civilizations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Creator Corner — synced from the "Sponsors & Creators" tab of the festival
-- sheet, with the option for admin overrides. Sheet is preseeded info; any row
-- the admin touches gets `admin_edited = 1` and stops being overwritten by the
-- next sheet sync. Admin can also add pure-DB rows (sheet_key NULL).
CREATE TABLE IF NOT EXISTS creators (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_key     TEXT,                                  -- "day|gmt|host" normalized; NULL = admin-only
    host          TEXT NOT NULL DEFAULT '',              -- creator name
    event         TEXT NOT NULL DEFAULT '',              -- what they're bringing (optional)
    day           TEXT NOT NULL DEFAULT '',              -- "Festival Day 1: Friday, 19 June 2026"
    gmt           TEXT NOT NULL DEFAULT '',
    est           TEXT NOT NULL DEFAULT '',
    pst           TEXT NOT NULL DEFAULT '',
    aest          TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',              -- portal hex (optional)
    link          TEXT NOT NULL DEFAULT '',              -- Twitch / YouTube / X / Discord etc.
    notes         TEXT NOT NULL DEFAULT '',              -- freeform admin note
    admin_edited  INTEGER NOT NULL DEFAULT 0,            -- 1 = sheet sync skips this row
    hidden        INTEGER NOT NULL DEFAULT 0,            -- 1 = admin suppressed it from the public list
    display_order INTEGER NOT NULL DEFAULT 100,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_creators_sheet_key
    ON creators(sheet_key) WHERE sheet_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_creators_hidden ON creators(hidden);

CREATE TRIGGER IF NOT EXISTS creators_updated_at
AFTER UPDATE ON creators
BEGIN
    UPDATE creators SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Audit log
CREATE TABLE IF NOT EXISTS admin_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT    NOT NULL,                -- 'approved', 'rejected', 'edited', 'deleted'
    target_id   INTEGER,                         -- civilizations.id
    target_type TEXT    DEFAULT 'civilization',
    notes       TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
