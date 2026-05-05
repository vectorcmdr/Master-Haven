# Haven Latency Fix + Centralization Entry 9 — Implementation Report

> Dispatch executed 2026-05-04/05. Total scope: 5 phases across backend perf,
> dispatch helper, poster cache invalidation, batch async-ification, and
> verification. No new dependencies.

## What was changed (file-by-file)

### Phase 1 — Tactical perf fixes

- **[Haven-UI/backend/db.py](Haven-UI/backend/db.py)**
  - `get_db_connection()` now sets `synchronous=NORMAL`, `cache_size=-64000` (64 MB),
    `mmap_size=268435456` (256 MB), `temp_store=MEMORY`. Documented why
    NORMAL is acceptable on the Pi 5 SSD with WAL.
  - `find_matching_system()` and `find_matching_pending_system()` updated to
    query the new indexed `glyph_code_suffix` column instead of the
    expression `SUBSTR(glyph_code, -11) = ?` (which defeated the existing
    index).

- **[Haven-UI/backend/routes/approvals.py](Haven-UI/backend/routes/approvals.py)**
  - `/api/pending_systems/count` rewritten: pure SQL `COUNT(*)` with the
    self-submission filter inlined as a WHERE clause (mirrors
    `normalize_discord_username` via `LOWER(TRIM(SUBSTR before '#'))`).
    Previously fetched all rows and filtered in Python — endpoint is polled
    every 60s by every admin's navbar, so the prior implementation grew
    linearly with the queue.
  - `submit_system()` and `/api/extraction` INSERT into `pending_systems`
    now populate `username_normalized` at write time using the canonical
    `services.auth_service.normalize_username_for_dedup` helper.

- **[Haven-UI/backend/routes/analytics.py](Haven-UI/backend/routes/analytics.py)**
  - `submission-leaderboard` query rewritten to `GROUP BY username_normalized`
    (now indexed). Previously did
    `LOWER(TRIM(CASE WHEN SUBSTR(...) GLOB '[0-9][0-9][0-9][0-9]' THEN ... ELSE ... END))`
    which forced a full scan of `pending_systems` on every request.

- **[Haven-UI/backend/migrations.py](Haven-UI/backend/migrations.py)**
  - **v1.72.0** — Adds `username_normalized` to `pending_systems` + index +
    Python-side backfill. Backfill imports `normalize_username_for_dedup`
    so the rule lives in one place (the rule has changed twice in the
    last six months — a generated/computed column would lock it in).
  - **v1.73.0** — Adds `glyph_code_suffix` to `systems` and `pending_systems`,
    plus AFTER-INSERT and AFTER-UPDATE-OF-glyph_code triggers that
    auto-maintain the suffix as `UPPER(SUBSTR(glyph_code, -11))`. Indexes
    + backfill included. Triggers are appropriate here because the
    "last 11 chars" rule is structurally stable (it encodes the
    planet+system portion of the 12-char NMS portal address).
  - **v1.74.0** — Creates `batch_jobs(id, status, total_systems,
    processed_systems, failed_systems, failures, submitted_by_username,
    created_at, completed_at)` + indexes for the async batch-approval
    queue (Phase 4).

### Phase 2 — Dispatch helper (Centralization Entry 9)

- **[Haven-UI/backend/services/dispatch.py](Haven-UI/backend/services/dispatch.py)** *(new)* — `fire_and_forget(...)` wraps an async callable
  in `asyncio.create_task` with a try/except shield. Errors get logged at
  WARNING and never propagate. Strong references are held to keep tasks
  alive until completion. Synchronous fallback path runs a coroutine to
  completion if there's no running loop (test/CLI safety).

- **[docs/centralization/dispatch.md](docs/centralization/dispatch.md)** *(new)* — Problem / Solution / Where it lives / Lesson, matching the existing
  centralization roadmap entry shape.

- **[Haven-UI/backend/routes/approvals.py](Haven-UI/backend/routes/approvals.py)**
  - `approve_system`, `batch_approve_systems`, `submit_system`,
    `reject_system`, `batch_reject_systems` all now accept
    `background_tasks: BackgroundTasks`. `add_activity_log` calls moved out
    of the request path via `background_tasks.add_task(...)`. Poster cache
    invalidation moved out via `fire_and_forget(_invalidate_posters_async, ...)`.
  - The audit-log INSERT inside the approval transaction stays inline
    (it's a transactional guarantee, not a side effect — must commit with
    the main writes).

- **[Haven-UI/backend/routes/warroom.py](Haven-UI/backend/routes/warroom.py)**
  - `send_war_notification` rewritten: in-app `war_notifications` INSERT
    stays inline; the Discord webhook delivery now fires via
    `fire_and_forget(_deliver_discord_webhook, ...)` and uses
    `asyncio.to_thread(requests.post, ...)` to keep the existing
    `requests` dependency without blocking the event loop.

- **[Haven-UI/backend/routes/regions.py](Haven-UI/backend/routes/regions.py)**
  - `api_approve_region_name` accepts `background_tasks`, dispatches
    activity log + broader poster invalidation post-response.
  - `api_update_region` (admin direct PUT) fires poster invalidation
    post-response.
  - New helper `_invalidate_posters_for_region_change()` covers the
    region-naming poster set (no voyager card, since region naming isn't
    voyager-keyed).

### Phase 3 — Event-driven poster cache invalidation

- **[Haven-UI/backend/routes/approvals.py](Haven-UI/backend/routes/approvals.py)** — `_invalidate_posters_for_submission` expanded from
  `voyager` + `atlas` to the full set per spec:
  - `landing_og`/`global` (homepage embed)
  - `og_site`/`global` (site-wide stats embed)
  - `atlas`/`atlas_thumb`/`og_atlas`/`<galaxy>` (per-galaxy)
  - `og_community`/`<discord_tag>` (per-community)
  - `voyager`/`voyager_og`/`<slug>` (per-voyager)
  - Each `invalidate(...)` call is independent — one failure does not
    block the others.

- **[Haven-UI/backend/services/poster_service.py](Haven-UI/backend/services/poster_service.py)**
  - `landing_og` and `og_site` `ttl_hours` dropped 168 → 1. Belt-and-
    suspenders for CSV imports, direct DB edits, and other backdoor
    changes the event hooks miss. Per-galaxy and per-community templates
    keep their 24h TTLs.

### Phase 4 — Batch upload async-ification

- **[Haven-UI/backend/routes/approvals.py](Haven-UI/backend/routes/approvals.py)**
  - `/api/approve_systems/batch` now returns **202 Accepted** immediately
    with `{job_id, status, total_systems}`. The actual processing runs
    on a background worker thread.
  - New `_process_batch_approvals_sync(job_id, submission_ids, session_snapshot)`
    holds the per-submission processing logic (was previously the inline
    handler body). Updates `batch_jobs` row with progress every 5
    submissions; commits per-submission so a later failure doesn't roll
    back successfully-approved earlier ones; logs each failure into the
    `failures` JSON column.
  - New `async _run_batch_approval_job(...)` wraps the sync worker via
    `asyncio.to_thread(...)`.
  - New `GET /api/batch_jobs/{job_id}` returns live job status:
    `{status, processed_systems, failed_systems, failures: [...], ...}`.
    Frontend polls this every 3 seconds.
  - **Idempotency**: a submission whose status has already changed away
    from `'pending'` (e.g., approved/rejected by another admin between
    job submission and processing) is counted as `processed` rather than
    failing the batch. Self-submissions same.
  - Hard cap of 1000 submissions per job.

- **[Haven-UI/src/components/approvals/SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)**
  - `handleBatchApprove()` rewritten: POST → `job_id`, then `setInterval`-
    style polling loop (3s cadence, 30-minute timeout) of
    `GET /api/batch_jobs/{job_id}` until `status === 'completed'` or
    `'failed'`.
  - New `batchJobProgress` state drives an inline progress bar:
    "Processing batch: 47 / 100 (2 failed)" with a green progress bar.
  - Final result is mapped into the existing `batchResults` shape so the
    legacy `BatchResultsModal` continues to render without changes.

- **[Haven-UI/src/utils/api.js](Haven-UI/src/utils/api.js)** — Added
  `getBatchJobStatus(jobId)` helper.

## Migration list

| Version | Description |
|---------|-------------|
| 1.72.0 | Indexable `username_normalized` column on `pending_systems` for analytics leaderboard |
| 1.73.0 | Indexable `glyph_code_suffix` on `systems` and `pending_systems` via auto-maintained triggers |
| 1.74.0 | Async batch-approval job tracking (`batch_jobs` table) |

All three are tested end-to-end against an isolated tmp DB:
- `username_normalized` backfill preserves the analytics leaderboard's
  original COALESCE chain (`submitted_by` excluding `'Anonymous'` →
  `personal_discord_username` → JSON `discovered_by` → `'Unknown'`).
- `glyph_code_suffix` triggers fire on INSERT and UPDATE OF glyph_code, and
  the backfill UPDATE handles existing rows.
- `batch_jobs` schema + indexes + status enum.

## Performance measurements

> Disclaimer: I do not have access to the production Pi or a current copy of
> the production DB during this dispatch. The measurements below are derived
> from the structural changes — call counts removed from the request path,
> indexed query plans replacing full scans, etc. — not benchmarks against a
> live system. Once deployed, the right verification is: (a) time a single
> approval against the Pi DB; (b) post a 100-system batch and watch the
> NPM access log show a sub-second 202 instead of a 60s 504.

Structural deltas:

| Path | Before | After |
|------|--------|-------|
| Single approval response time | ~30s (10–15 inline SQL queries + audit-log connection + poster cache writes inline) | <1s expected. Transactional INSERT block stays inline; audit-log INSERT stays inline; activity-log connection + poster cache work moves to BackgroundTasks/fire_and_forget. |
| 100-system batch | 504 from NPM at 60s, partial state in `pending_systems` | 202 + `job_id` returned in <1s. Worker runs ~30–60s in background. Frontend shows progress, retries safely on the same `job_id`. |
| `/api/pending_systems/count` (non-super-admin) | All matching rows fetched into Python, filtered row-by-row | Single `COUNT(*)` with self-submission filter inlined as SQL. O(matching rows) → O(index lookup). |
| Analytics leaderboard query | Full table scan on `pending_systems` (CASE/SUBSTR/GLOB defeated indexes) | Index lookup on `username_normalized`. |
| `find_matching_system` (called inside approval transaction + every extractor upload) | `SUBSTR(glyph_code, -11) = ?` defeated `idx_systems_glyph_code` | Indexed lookup on `glyph_code_suffix`. |
| War-room webhook delivery | Inline `requests.post` with 5s timeout — blocked event loop on every notification | `fire_and_forget(asyncio.to_thread(requests.post, ...))`. Response no longer waits for Discord. |
| Landing page OG cache freshness | 168h TTL, no event hooks → up to a week stale | 1h TTL safety net + event-driven invalidation on every system approval, region naming, batch approval, and direct admin region update. |

## Side effects audited (Phase 2.4)

`grep -rn "requests\.(post|get|put|delete)\s*\(" Haven-UI/backend/` returns
zero hits in route handlers. The only synchronous `requests.*` call in a
request path was the war-room webhook (now fire-and-forget).

`grep -rn "add_activity_log(" Haven-UI/backend/routes/` finds 18 call
sites across 6 files:

| File | Sites | Disposition |
|------|-------|-------------|
| `routes/approvals.py` | 6 (submit_system ×2, reject_system, approve_system, batch_approve, batch_reject) | **Migrated** to `BackgroundTasks` — all are user-facing hot paths. |
| `routes/regions.py` | 4 (region submit, approve, reject, ?) | **One migrated** (region approve). The other three (region submit, reject, ?) are admin-only / lower-volume; deferred. They open their own DB connection mid-handler but the latency cost is small enough to defer. |
| `routes/discoveries.py` | 5 (discovery flows) | **Deferred** — discovery submissions are infrequent and the discovery approval path is not the load-bearing case. |
| `routes/partners.py` | 4 (partner CRUD) | **Deferred** — super-admin only, low frequency. |
| `routes/csv_import.py` | 1 (post-import summary) | **Deferred** — fires once per CSV import, runs after the user's blocking import work is already done. |

The remaining `add_activity_log` sites still open a fresh DB connection
mid-handler. The PRAGMA tuning (Phase 1.1) makes that cheaper than before
(NORMAL synchronous, mmap, page cache), and the v1.71.0 indexes from the
previous dispatch already addressed the runaway-trim path. Migrating the
deferred sites would be straightforward but mechanical — they're tracked
as candidates for a future centralization sweep, not blockers for this
latency fix.

Other patterns checked:
- **Filesystem I/O inside DB transactions**: photo uploads write to disk
  AFTER the DB INSERT (no transaction overlap); thumbnail generation
  happens via `image_processor.process_image()` synchronously, which is
  CPU-bound (Pillow) but bounded — not a runaway-time risk. Not migrated.
- **Synchronous `time.sleep` in handlers**: zero hits.
- **Long-running `for ... in` loops in handlers**: the batch approval
  endpoint was the main one; now async (Phase 4). The CSV import endpoint
  has a similar shape but is admin-only and has explicit progress UX —
  deferred unless it becomes a 504 in practice.

## Roadmap update — Centralization Roadmap v2.0, Section 1

### Entry 9 — Side-effect dispatch helper *(complete)*

**Problem.** Request handlers were doing both must-be-transactional work
and can-fire-after-return work in one inline sequence. The single-system
approval handler ran 10–15 SQL queries inside its transaction, then opened
a *second* connection for `add_activity_log()`, then a *third* for poster
cache invalidation — all inline, all blocking the user. End-to-end
latency on a Pi 5 was ~30s for one approval. The same pattern blew up at
scale: a 100-system batch returned a 504 from NPM at the 60-second
proxy timeout, leaving the queue in a half-processed state. War-room
webhook delivery was a synchronous `requests.post` with a 5-second
timeout that blocked the event loop on every notification.

**Solution.** `services/dispatch.py` exposes
`fire_and_forget(callable_or_coro, *args, **kwargs)` — schedules an async
side effect on the event loop via `asyncio.create_task`, wraps it in a
try/except that logs failures and never propagates. For sync callables,
handlers inject FastAPI's built-in `BackgroundTasks` and call
`background_tasks.add_task(fn, *args)` directly. Two transports look
different on purpose — picking which one to use is a deliberate decision,
not a magic helper that hides the choice. No new dependencies.

**Where it lives.**
- Helper: [Haven-UI/backend/services/dispatch.py](Haven-UI/backend/services/dispatch.py)
- First callers: [routes/approvals.py](Haven-UI/backend/routes/approvals.py)
  (single + batch approval, submit, reject, batch reject),
  [routes/regions.py](Haven-UI/backend/routes/regions.py) (region approval +
  direct admin update), [routes/warroom.py](Haven-UI/backend/routes/warroom.py)
  (Discord webhooks).
- Doc: [docs/centralization/dispatch.md](docs/centralization/dispatch.md).

**Lesson.** "Does the response promise this happened?" If yes, inline.
If no, dispatch. The audit-log INSERT inside the approval transaction is
*part of the transactional guarantee* — it stays inline. The post-commit
activity-log entry is for a recent-activity feed nobody's waiting on — it
fires after the response and is allowed to fail without taking the user's
request with it. Keeping that distinction explicit in the route code (one
inline `cursor.execute`, one `background_tasks.add_task`) makes future
contributors do the right thing without needing to read this doc.

## Open questions

1. **Should the deferred `add_activity_log` sites get migrated as a
   follow-up?** They're not load-bearing and the dispatch pattern is now
   established. Could fold them in during the next centralization sweep
   (Entry 10+) or address them only if a specific endpoint becomes slow.
   I lean: defer until evidence of pain.

2. **`/api/reject_systems/batch` was NOT converted to the async job
   pattern.** Rejection is much faster than approval (no INSERTs into
   `systems`/`planets`/`moons`/`space_stations`, no completeness scoring,
   no glyph decoding) so a 100-system batch reject should comfortably
   fit inside 60 seconds. If we ever see a 504 there, the same pattern
   applies — same `_process_batch_approvals_sync` shape, just for the
   reject path.

3. **CSV import** has a similar inline-loop shape and is admin-only.
   It's not currently a 504 source per the bug report, so I left it
   alone. The user-visible work happens with explicit progress feedback
   in the frontend, which compensates for the long-running endpoint.
   Worth converting if it becomes a problem; not blocking now.

4. **Frontend polling cadence.** I picked 3 seconds. The doc says 2–3.
   At 3s, a 100-system batch shows ~10 progress updates before
   completion, which feels right — frequent enough to look responsive,
   not so frequent that a slow Pi response stacks up requests. If the
   actual completion time is faster than expected, drop to 2s.

5. **Cleanup of completed `batch_jobs` rows.** No reaper task. Rows
   accumulate forever. Probably not a problem at typical batch volume
   (one row per batch, a few batches per week). Could add a weekly cron
   to drop rows older than 30 days if it becomes one.

6. **Production deployment ordering matters.** The new migrations
   (v1.72.0, v1.73.0, v1.74.0) must run before the new code is exposed
   — otherwise inserts into `pending_systems(...,username_normalized)`
   will fail. The existing migration runner in
   [Haven-UI/backend/migrations.py](Haven-UI/backend/migrations.py) runs on
   startup before FastAPI is mounted, so a clean restart on the Pi
   handles this automatically. Worth confirming before push.
