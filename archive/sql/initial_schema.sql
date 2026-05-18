-- =====================================================================
-- TRAVELERS ARCHIVE — PHASE 3: DATA MODEL SCHEMA (SQLite)
-- =====================================================================
--
-- SQLite schema derived from v0.8 mockup design and Phase 2 workflows.
--
-- Design principles:
-- 1. Stories, inquisitions, and encyclopedia entities are three parallel
--    content types. All three can reference civilizations and people.
-- 2. Drafts are a separate concept that becomes a published record on
--    publish. Drafts have status, comments, and co-authors.
-- 3. Soft delete only — `deleted_at` nullable.
-- 4. Discord username is the cross-system join key with Haven Control Room.
-- 5. Timestamps are TEXT in ISO 8601 (SQLite has no native datetime).
--
-- Conventions:
-- - Table names: snake_case, singular
-- - Primary keys: INTEGER PRIMARY KEY AUTOINCREMENT
-- - Foreign keys: always {table}_id, FK constraints on
-- - Booleans: INTEGER 0/1
-- - Timestamps: TEXT, default CURRENT_TIMESTAMP
-- - Soft delete: deleted_at nullable
-- - JSON fields: TEXT, validated at app layer
--
-- Total tables: 17. Estimated storage at 5-year mark: <5GB before media.
-- =====================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- =====================================================================
-- SECTION 1: USERS AND ROLES
-- =====================================================================

CREATE TABLE archive_user (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL UNIQUE,
    discord_username TEXT NOT NULL,            -- the @-handle, lowercase
    display_name    TEXT NOT NULL,
    avatar_url      TEXT,
    avatar_letter   TEXT,                      -- single letter for fallback avatar
    avatar_color    TEXT,                      -- color slug: purple, pink, teal, etc.
    bio             TEXT,
    civ_slug        TEXT,                      -- which civ they belong to (FK to civilization)
    beat            TEXT,                      -- e.g., "The Galactic Hub" — for diplomats
    base_role       TEXT NOT NULL DEFAULT 'reader' CHECK(base_role IN ('reader', 'diplomat', 'historian')),
    is_editor       INTEGER NOT NULL DEFAULT 0 CHECK(is_editor IN (0, 1)),
    is_admin        INTEGER NOT NULL DEFAULT 0 CHECK(is_admin IN (0, 1)),
    last_login      TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);

CREATE INDEX idx_user_discord ON archive_user(discord_id);
CREATE INDEX idx_user_civ ON archive_user(civ_slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_user_editors ON archive_user(is_editor) WHERE is_editor = 1 AND deleted_at IS NULL;


-- Discord role sync log — track when each Discord role pull happened
CREATE TABLE discord_sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    server          TEXT NOT NULL CHECK(server IN ('vh', 'archivist')),
    started_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TEXT,
    users_added     INTEGER NOT NULL DEFAULT 0,
    users_updated   INTEGER NOT NULL DEFAULT 0,
    users_removed   INTEGER NOT NULL DEFAULT 0,
    error           TEXT
);


-- =====================================================================
-- SECTION 2: ENCYCLOPEDIA ENTITIES
-- =====================================================================

CREATE TABLE civilization (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'dormant', 'archived')),
    galaxy          TEXT,                      -- "Euclid", "Hilbert", etc., or "Multi-galaxy"
    founded         TEXT,                      -- "c. 2017" or "2025" — display string
    founded_year    INTEGER,                   -- structured year for sorting/filtering
    ended           TEXT,                      -- "2022" if dormant/archived
    ended_year      INTEGER,
    tagline         TEXT,                      -- one-line summary
    description     TEXT,                      -- multi-paragraph overview
    color_primary   TEXT NOT NULL DEFAULT '#534AB7',  -- hex
    color_secondary TEXT NOT NULL DEFAULT '#1D9E75',
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by      INTEGER REFERENCES archive_user(id),
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);

CREATE INDEX idx_civ_status ON civilization(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_civ_slug ON civilization(slug) WHERE deleted_at IS NULL;


CREATE TABLE person (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,             -- display name; can be a handle or real name
    discord_username TEXT,                     -- if known, for cross-reference to archive_user
    civ_slug        TEXT,                      -- primary civ affiliation
    role_in_civ     TEXT,                      -- "founder", "leader", "member", etc.
    bio             TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by      INTEGER REFERENCES archive_user(id),
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);

CREATE INDEX idx_person_slug ON person(slug) WHERE deleted_at IS NULL;
CREATE INDEX idx_person_civ ON person(civ_slug) WHERE deleted_at IS NULL;


CREATE TABLE event (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    event_date      TEXT,                      -- ISO 8601 if exact, else display string
    event_year      INTEGER,                   -- structured year for sorting
    description     TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by      INTEGER REFERENCES archive_user(id),
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);

CREATE INDEX idx_event_year ON event(event_year) WHERE deleted_at IS NULL;


CREATE TABLE place (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    galaxy          TEXT,
    region          TEXT,
    coordinates     TEXT,                      -- glyphs or galactic address as text
    description     TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by      INTEGER REFERENCES archive_user(id),
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);


-- =====================================================================
-- SECTION 3: STORIES (BRIEFS AND FEATURES)
-- =====================================================================

CREATE TABLE story (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    doctype         TEXT NOT NULL CHECK(doctype IN ('brief', 'feature')),
    headline        TEXT NOT NULL,
    deck            TEXT,                      -- subtitle / standfirst
    body            TEXT NOT NULL,             -- markdown
    beat            TEXT,                      -- "civupdates", "diplomacy", "events", etc.
    author_id       INTEGER NOT NULL REFERENCES archive_user(id),
    published_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_minutes    INTEGER,                   -- null for briefs, computed for features
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);

CREATE INDEX idx_story_published ON story(published_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_story_doctype ON story(doctype) WHERE deleted_at IS NULL;
CREATE INDEX idx_story_beat ON story(beat) WHERE deleted_at IS NULL;
CREATE INDEX idx_story_author ON story(author_id) WHERE deleted_at IS NULL;


-- Stories link to civilizations (many-to-many)
CREATE TABLE story_civilization (
    story_id        INTEGER NOT NULL REFERENCES story(id) ON DELETE CASCADE,
    civ_slug        TEXT NOT NULL,
    PRIMARY KEY (story_id, civ_slug)
);

CREATE INDEX idx_story_civ_lookup ON story_civilization(civ_slug);


-- =====================================================================
-- SECTION 4: INQUISITIONS
-- =====================================================================

CREATE TABLE inquisition (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    numeral         TEXT NOT NULL UNIQUE,      -- Roman numeral, e.g., "XLVII"
    title           TEXT NOT NULL,
    subtitle        TEXT,
    deck            TEXT,
    body            TEXT NOT NULL DEFAULT '',  -- markdown, can be very long
    state           TEXT NOT NULL DEFAULT 'in_progress' CHECK(state IN ('in_progress', 'closed', 'archived')),
    progress        INTEGER NOT NULL DEFAULT 0 CHECK(progress >= 0 AND progress <= 100),
    sources_count   INTEGER NOT NULL DEFAULT 0,
    started_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at       TEXT,
    lead_author_id  INTEGER NOT NULL REFERENCES archive_user(id),
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);

CREATE INDEX idx_inq_state ON inquisition(state) WHERE deleted_at IS NULL;
CREATE INDEX idx_inq_started ON inquisition(started_at DESC) WHERE deleted_at IS NULL;


-- Inquisition co-authors
CREATE TABLE inquisition_author (
    inquisition_id  INTEGER NOT NULL REFERENCES inquisition(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES archive_user(id),
    added_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (inquisition_id, user_id)
);


-- Inquisitions link to civilizations
CREATE TABLE inquisition_civilization (
    inquisition_id  INTEGER NOT NULL REFERENCES inquisition(id) ON DELETE CASCADE,
    civ_slug        TEXT NOT NULL,
    PRIMARY KEY (inquisition_id, civ_slug)
);

CREATE INDEX idx_inq_civ_lookup ON inquisition_civilization(civ_slug);


-- =====================================================================
-- SECTION 5: DRAFTS
-- =====================================================================
-- Drafts are work-in-progress versions of stories OR inquisitions.
-- When published, they become a row in `story` or `inquisition` and the
-- draft is archived (kept for audit, marked published_as).
-- =====================================================================

CREATE TABLE draft (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    doctype         TEXT NOT NULL CHECK(doctype IN ('brief', 'feature', 'inquisition')),
    headline        TEXT,
    deck            TEXT,
    body            TEXT NOT NULL DEFAULT '',
    beat            TEXT,                      -- only for stories
    numeral         TEXT,                      -- only for inquisitions, assigned at "open" time
    status          TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'in_review', 'returned', 'ready', 'published')),
    author_id       INTEGER NOT NULL REFERENCES archive_user(id),
    reviewed_by_id  INTEGER REFERENCES archive_user(id),
    reviewed_at     TEXT,
    published_as_story_id INTEGER REFERENCES story(id),
    published_as_inquisition_id INTEGER REFERENCES inquisition(id),
    last_edited_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);

CREATE INDEX idx_draft_author ON draft(author_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_draft_status ON draft(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_draft_review_queue ON draft(status, last_edited_at)
    WHERE status = 'in_review' AND deleted_at IS NULL;


-- Co-authors on a draft (full edit access)
CREATE TABLE draft_coauthor (
    draft_id        INTEGER NOT NULL REFERENCES draft(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES archive_user(id),
    added_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    added_by_id     INTEGER NOT NULL REFERENCES archive_user(id),
    PRIMARY KEY (draft_id, user_id)
);


-- Drafts link to civilizations (the civ tag visible in mockup byline)
CREATE TABLE draft_civilization (
    draft_id        INTEGER NOT NULL REFERENCES draft(id) ON DELETE CASCADE,
    civ_slug        TEXT NOT NULL,
    PRIMARY KEY (draft_id, civ_slug)
);


-- Comments on drafts. Either inline (anchored to a quoted phrase) or
-- document-level (quoted_text NULL).
CREATE TABLE draft_comment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id        INTEGER NOT NULL REFERENCES draft(id) ON DELETE CASCADE,
    author_id       INTEGER NOT NULL REFERENCES archive_user(id),
    body            TEXT NOT NULL,
    quoted_text     TEXT,                      -- the phrase from the draft body, if inline
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);

CREATE INDEX idx_comment_draft ON draft_comment(draft_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_comment_author ON draft_comment(author_id);


-- =====================================================================
-- SECTION 6: NOTIFICATIONS
-- =====================================================================

CREATE TABLE notification (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES archive_user(id),
    type            TEXT NOT NULL CHECK(type IN (
                        'coauthor_added',
                        'draft_submitted',     -- to editors
                        'draft_returned',      -- to author
                        'draft_marked_ready',  -- to author
                        'comment_mention',
                        'watchlist_update'
                    )),
    title           TEXT NOT NULL,
    body            TEXT,
    link            TEXT,                      -- internal route, e.g., "/draft/47"
    related_draft_id INTEGER REFERENCES draft(id),
    related_user_id INTEGER REFERENCES archive_user(id),
    is_read         INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0, 1)),
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notif_user_unread ON notification(user_id, is_read, created_at DESC)
    WHERE is_read = 0;


-- =====================================================================
-- SECTION 7: WATCHLIST
-- =====================================================================
-- Users can watch entities and inquisitions. They get notifications
-- when watched items change.
-- =====================================================================

CREATE TABLE watchlist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES archive_user(id) ON DELETE CASCADE,
    target_type     TEXT NOT NULL CHECK(target_type IN ('civilization', 'person', 'event', 'place', 'inquisition', 'user')),
    target_id       INTEGER NOT NULL,          -- polymorphic; app layer enforces FK
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, target_type, target_id)
);

CREATE INDEX idx_watchlist_user ON watchlist(user_id);
CREATE INDEX idx_watchlist_target ON watchlist(target_type, target_id);


-- =====================================================================
-- SECTION 8: REVISIONS (encyclopedia entities only)
-- =====================================================================
-- Stories and inquisitions don't have a wiki-style revision history.
-- Only encyclopedia entities (civ, person, event, place) do.
-- =====================================================================

CREATE TABLE entity_revision (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT NOT NULL CHECK(entity_type IN ('civilization', 'person', 'event', 'place')),
    entity_id       INTEGER NOT NULL,
    changed_by_id   INTEGER NOT NULL REFERENCES archive_user(id),
    change_summary  TEXT,                      -- one-line description of what changed
    snapshot_json   TEXT NOT NULL,             -- full JSON snapshot of the entity after change
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_revision_entity ON entity_revision(entity_type, entity_id, created_at DESC);


-- =====================================================================
-- SECTION 9: MEDIA
-- =====================================================================

CREATE TABLE media_asset (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    storage_path    TEXT NOT NULL,             -- relative path inside ~/docker/archive-data/media/
    mime_type       TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    width           INTEGER,
    height          INTEGER,
    alt_text        TEXT,
    uploaded_by_id  INTEGER NOT NULL REFERENCES archive_user(id),
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);


-- Media can be referenced by stories, inquisitions, drafts, or entities
CREATE TABLE media_attachment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id        INTEGER NOT NULL REFERENCES media_asset(id) ON DELETE CASCADE,
    target_type     TEXT NOT NULL CHECK(target_type IN ('story', 'inquisition', 'draft', 'civilization', 'person', 'event', 'place')),
    target_id       INTEGER NOT NULL,
    role            TEXT,                      -- "hero", "inline", "thumbnail"
    sort_order      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_media_target ON media_attachment(target_type, target_id);


-- =====================================================================
-- SECTION 10: SOURCES (light version — no per-claim citation)
-- =====================================================================
-- Required on inquisitions and entity pages. Optional on stories
-- (sources implied by byline for stories).
-- =====================================================================

CREATE TABLE source (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    url             TEXT,                      -- if web-accessible
    source_type     TEXT NOT NULL CHECK(source_type IN ('discord', 'reddit', 'forum', 'wiki', 'video', 'screenshot', 'interview', 'other')),
    quality         TEXT NOT NULL DEFAULT 'community' CHECK(quality IN ('primary', 'secondary', 'community', 'rotted')),
    notes           TEXT,
    archived_url    TEXT,                      -- Wayback Machine URL if URL is at risk
    added_by_id     INTEGER NOT NULL REFERENCES archive_user(id),
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TEXT
);


-- Source can be cited by inquisitions or entity pages
CREATE TABLE source_citation (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER NOT NULL REFERENCES source(id) ON DELETE CASCADE,
    target_type     TEXT NOT NULL CHECK(target_type IN ('inquisition', 'civilization', 'person', 'event', 'place')),
    target_id       INTEGER NOT NULL,
    note            TEXT,                      -- which claim does this support
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_citation_target ON source_citation(target_type, target_id);


-- =====================================================================
-- SECTION 11: AUDIT LOG
-- =====================================================================

CREATE TABLE audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES archive_user(id),
    action          TEXT NOT NULL,             -- "draft.publish", "user.role_changed", etc.
    target_type     TEXT,
    target_id       INTEGER,
    metadata_json   TEXT,                      -- arbitrary JSON for context
    ip_address      TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_log(action, created_at DESC);


-- =====================================================================
-- END SCHEMA
-- =====================================================================
-- Total tables: 17 (verification will count 17 user tables; SQLite
-- internally adds `sqlite_sequence` for AUTOINCREMENT support and
-- Alembic adds `alembic_version` after this migration runs).
-- =====================================================================
