# Master Haven — Full Audit Report
**Date:** 2026-05-13
**Scope:** Haven-UI frontend + Backend API/DB wiring + Mobile responsive polish
**Method:** 6 parallel specialized audit agents (auth, submit/wizard, approvals, browse, admin, mobile)
**Type:** Read-only audit — no code changes made

---

## TL;DR

**~125 unique findings** across all tiers (public / member / sub-admin / partner / super-admin) after deduplication.

| Severity | Count | Meaning |
|----------|-------|---------|
| CRITICAL | 13    | Data leak, auth bypass, silent data loss, transaction integrity |
| HIGH     | 35    | Feature broken for a tier, wrong data persisted, scoping gap |
| MEDIUM   | 44    | Edge case, missing field, UX gap that doesn't lose data |
| LOW      | 31    | Polish, dead code, minor inconsistency |
| POLISH   | 2     | Pure visual / class-name |

### Top 10 to fix first (by impact-to-effort ratio)

1. **CRITICAL** — `/api/keys*` endpoints accept any logged-in user (incl. tier-5 readonly members). Mint/list/revoke API keys with a session cookie. → [extractor.py:47, 121, 171, 208](Haven-UI/backend/routes/extractor.py)
2. **CRITICAL** — `discoveries_draft` silently dropped in Wizard when public submitter goes through profile-claim modal. Exact bug v1.64.0 was meant to fix. → [Wizard.jsx:836-841, 938-970](Haven-UI/src/pages/Wizard.jsx)
3. **CRITICAL** — `submit_system` INSERT into `pending_systems` omits `glyph_code` column → wizard pending rows have NULL `glyph_code_suffix` → dedup never matches them. Two simultaneous Wizard submissions for the same system both go pending. → [approvals.py:617](Haven-UI/backend/routes/approvals.py)
4. **CRITICAL** — `GET /api/pending_systems/{id}` and `GET /api/pending_discoveries/{id}` have no community scoping. Partner from civ A can iterate IDs and read civ B's full pending submission data. → [approvals.py:976](Haven-UI/backend/routes/approvals.py), [discoveries.py:867](Haven-UI/backend/routes/discoveries.py)
5. **CRITICAL** — Partner can grant features beyond own `enabled_features` via `PUT /api/admin/profiles/{id}` → self-elevate sub-admins to CSV import / war room / batch approvals. → [profiles.py:972-1070](Haven-UI/backend/routes/profiles.py)
6. **CRITICAL** — Region name single-approve and single-reject endpoints have **no self-approval check at all**. Sub-admin submits region name, then approves their own. → [regions.py:1325, 1438](Haven-UI/backend/routes/regions.py)
7. **CRITICAL** — `save_system` orphans moon rows on edit (admin direct-create path) — DELETEs planets without first DELETEing moons. With FKs OFF (next item), every edit leaks. → [control_room_api.py:2711](Haven-UI/backend/control_room_api.py)
8. **CRITICAL** — SQLite `PRAGMA foreign_keys = ON` is **never enabled** anywhere. Every `ON DELETE CASCADE` in the schema is dead code. One PRAGMA fixes a whole class of orphan-row bugs. → [db.py](Haven-UI/backend/db.py)
9. **CRITICAL** — `/api/pending_edits/*` endpoints (super-admin) approve does NOT actually apply the edit; neither approve nor reject writes to audit log. UI lies to partners. → [partners.py:995-1061](Haven-UI/backend/routes/partners.py)
10. **CRITICAL** — `/api/discord_tag_colors` still reads from `partner_accounts` (legacy). Civs created via CivilizationManagement get NO color anywhere (region overlays, OG posters, theme). Flagged in project memory as known follow-up — still unfixed. → [partners.py:1203-1237](Haven-UI/backend/routes/partners.py)

### Cross-cutting themes (fix the pattern, not just the instance)

- **Legacy `partner_accounts` reads vs `civilizations` writes** — region color, war room enrollment, audit-source filter, sub-admin enabled_features. Civs created since v1.80.0 silently miss multiple features.
- **Self-approval prevention has 5+ inline implementations** that diverge — `check_self_submission()` is the canonical helper but several endpoints either skip it (region name approve/reject), use stale inline copies (`reject_discovery`), or exempt entire tiers (`partner` tier exempted in the helper itself).
- **Detail endpoints lack the scoping their list endpoints have** — `/api/pending_systems/{id}`, `/api/pending_discoveries/{id}`, `/api/admin/profiles/{id}`, `/api/batch_jobs/{id}`. Pattern: list scopes properly, detail leaks.
- **INSERT column-list drift across 4 paths** for `systems` / `planets` / `moons` / `pending_systems` — every new column needs to be added to `save_system` / `approve_system` / `batch_approve` / `/api/extraction`. Currently `game_mode`, `glyph_code`, moon biome fields, `game_version`, `expedition_id` are missing from at least one path each.
- **SystemDetail page is missing 4 features the changelog claims it has**: game_mode badge, completeness_breakdown panel, space_station card, system discoveries list. All backend data is returned; frontend never reads it.
- **Mobile: hard inline `gridTemplateColumns: 'NNNpx NNNpx'` and `min-w-[NNNpx]` without breakpoints** — Wizard 1.52.1 fix was for one occurrence; the same pattern lives in WarRoom, CSV Import, SearchableSelect, hub pages.
- **Extractor enum-prefix string contamination** is solved at the layer-2 backend (v1.59.0 `normalize_reality()`) — but no other extractor enum field has the same intake guard. Same pattern can recur with `community_tag` / `game_mode`.

---

## Findings by area

### 1. AUTH, TIER SCOPING, PERMISSION GUARDS

#### CRITICAL
- **`/api/keys*` endpoints accept any logged-in user (incl. tier-5)** — POST/GET/DELETE/PUT all gate on `verify_session()` only. Frontend `RequireSuperAdmin` is the only gate; a member with a session cookie can curl and mint/list/revoke any key. Same shape on `routes/regions.py:1058, 1116` (region PUT/DELETE name). → [extractor.py:47, 121, 171, 208](Haven-UI/backend/routes/extractor.py) — **Fix:** swap `verify_session()` for `is_super_admin()` (or tier-conditional) on all four.

- **Analytics endpoints leak cross-community data** — every `/api/analytics/*` endpoint uses `if not is_super and user_discord_tag: discord_tag = user_discord_tag`. If the session has `user_discord_tag = None` (Haven sub-admin pre-civ, member with no `default_civ_tag`, partner whose tag got cleared), the override never fires and the caller-supplied query param flows into SQL. Endpoints also have no admin tier gate beyond "session exists" — a member can curl `/api/analytics/submission-leaderboard?discord_tag=Haven` directly. → [analytics.py:51, 374, 456, 529, 666, 779, 850, 933](Haven-UI/backend/routes/analytics.py) — **Fix:** add explicit member tier rejection + change scoping to `discord_tag = user_discord_tag or '__no_access__'` on missing tag.

- **Legacy partner sessions can edit Haven sub-admin profiles via NULL == NULL match** — permission check `if row['parent_profile_id'] != session.profile_id`. Legacy `partner_accounts` login never sets `profile_id`, Haven sub-admins have NULL `parent_profile_id`. `None != None` is False → check passes. Legacy partner can call `PUT /api/admin/profiles/{haven_sub_admin_id}` to edit features/password. → [profiles.py:996, 1097](Haven-UI/backend/routes/profiles.py) — **Fix:** explicit None guard before equality compare.

#### HIGH
- **`check_self_submission` exempts ALL partners** — partner can approve their own submissions defeating peer review. `co-author` check correctly only exempts super_admin. → [auth_service.py:236-238](Haven-UI/backend/services/auth_service.py)
- **`/api/profiles/me/set-password` allows password set without current-password if `password_hash IS NULL`, with no tier check** — admin tier with NULL hash can have password reset by anyone with that session. → [profiles.py:599-661](Haven-UI/backend/routes/profiles.py)
- **`/api/admin/profiles` partner scoping leaks members who happen to have submitted under that partner's tag** — but invisible to own sub-admins who haven't yet submitted. → [profiles.py:702-710](Haven-UI/backend/routes/profiles.py)
- **`/api/profile/login` silently downgrades tier-4 to readonly** if password not provided — UX trap. → [profiles.py:285-287](Haven-UI/backend/routes/profiles.py)
- **`/api/profiles/lookup` is unauthenticated and returns admin-tier data** — username enumeration toolkit. Anyone can probe "Stars" / "Parker1920" and learn tier=1. → [profiles.py:43-98](Haven-UI/backend/routes/profiles.py)
- **`civ_scope_filter` reads `civ_tags` from session that's only refreshed at login** — if a partner removes a sub-admin from a civ, sub-admin keeps approving until logout. → [auth.py:217-219](Haven-UI/backend/routes/auth.py)

#### MEDIUM
- `/api/discord_tag_colors` is public and exposes which civs are active partners — fine for map use case, flag for awareness. → [partners.py:1203-1237](Haven-UI/backend/routes/partners.py)
- `/api/admin/profiles/{id}` returns full metadata to any partner without scoping — cross-partner intel leak. → [profiles.py:765-853](Haven-UI/backend/routes/profiles.py)
- Sub-admin login response missing `tier`/`profile_id`/`default_civ_tag` etc. — defaults to null until next page reload. → [auth.py:399-404](Haven-UI/backend/routes/auth.py)
- `apply_data_restrictions` `point_only` mode retains glyph-derivable info; not all detail endpoints verified to call the restriction service. → [restrictions.py:210-230](Haven-UI/backend/services/restrictions.py)
- `/api/communities` filters on `is_active=1` but `/api/submit_system` never validates `discord_tag` against active civs — orphan submissions accumulate under deactivated tags. → [extractor.py:392](Haven-UI/backend/routes/extractor.py)
- `/api/profiles/use` claim endpoint returns admin-tier data without auth. → [profiles.py:174-222](Haven-UI/backend/routes/profiles.py)
- Sessions are per-worker in-memory module-global dict — multi-worker FastAPI deployment would break `set_active_civ`. Document single-worker requirement. → [auth_service.py:38](Haven-UI/backend/services/auth_service.py)

#### LOW
- `change_username` only supports legacy `partner_accounts` table; tier-2 user_profiles partner gets 404. → [auth.py:676-756](Haven-UI/backend/routes/auth.py)
- `/api/admin/profiles/{id}/tier` partner-discord-tag uniqueness check has TOCTOU race. → [profiles.py:893](Haven-UI/backend/routes/profiles.py)
- AuthContext has no global 401 handler — session expiry leaves stale UI showing admin features. → [AuthContext.jsx](Haven-UI/src/utils/AuthContext.jsx)

---

### 2. SUBMISSION FLOW (WIZARD) + DB COLUMN WIRING ON WRITES

#### CRITICAL
- **`discoveries_draft` silently dropped on profile-claim flow** — exactly the bug v1.64.0 was meant to fix. In `doSubmit()` the wizard stashes `pendingSubmitPayload` BEFORE the discoveries_draft array is constructed. `handleProfileUse` / `handleProfileCreatedContinue` resubmit the stashed payload, so every co-submitted discovery is silently dropped for any user going through the profile-claim modal. → [Wizard.jsx:836-841, 860-866, 938-939, 969-970](Haven-UI/src/pages/Wizard.jsx) — **Fix:** build `discoveries_draft` BEFORE the profile-lookup block, OR re-construct in the resubmit handlers.

- **SQLite foreign keys never enabled** — every `ON DELETE CASCADE` in the schema is dead code. Any DELETE on `planets` that doesn't first DELETE moons leaves orphans. → [db.py](Haven-UI/backend/db.py) — **Fix:** `cursor.execute("PRAGMA foreign_keys = ON")` immediately after every `get_db_connection()`.

- **`save_system` orphans moon rows on edit** — DELETEs planets at line 2711 without first DELETEing moons. With FKs off (above), every edit leaks. Compare to `approve_system` and `batch_approve` which do per-planet moon DELETEs first. → [control_room_api.py:2711](Haven-UI/backend/control_room_api.py)

#### HIGH
- **Wizard `submit_system` never inserts `glyph_code` column** → pending rows get NULL `glyph_code_suffix` → `find_matching_pending_system` can't find them. Two simultaneous Wizard submissions for the same system both go pending instead of merging. Extraction does this correctly. → [approvals.py:615-641](Haven-UI/backend/routes/approvals.py)
- **`approve_system` inserts duplicate space_stations on edit-resubmit** — no `DELETE FROM space_stations WHERE system_id = ?` before INSERT on `is_edit=True`. Same pattern as Bug-005 (moons) but for stations. `batch_approve` has the DELETE at line 2594. → [approvals.py:1818-1834](Haven-UI/backend/routes/approvals.py)
- **Region name uniqueness check ignores reality+galaxy scope** — `WHERE custom_name = ?` without joining on reality/galaxy. The UNIQUE constraint is 5-key; same name in different galaxy should be allowed but is currently blocked with 409. → [regions.py:1077, 1186](Haven-UI/backend/routes/regions.py)
- **`save_system` moon INSERT missing 8 fields** — biome, biome_subtype, weather, planet_size, common/uncommon/rare/plant resources. Approval paths persist them, partner direct-create silently loses moon biome data. → [control_room_api.py:2855](Haven-UI/backend/control_room_api.py)
- **`save_system` never sets `game_mode` column** — partner direct-create lands as `'Normal'` regardless of payload. → [control_room_api.py:2728-2767](Haven-UI/backend/control_room_api.py)
- **`submit_system` never persists `game_mode` to pending column** — only stored inside `system_data` JSON. Approval reviewer can't see/filter without parsing JSON. → [approvals.py:617](Haven-UI/backend/routes/approvals.py)
- **`_promote_draft_discoveries` swallows per-entry exceptions silently** — same silent-drop failure mode v1.64.0 was meant to eliminate. → [approvals.py:341-345](Haven-UI/backend/routes/approvals.py)
- **`/api/discoveries` hardcodes `submitter_profile_id = NULL`** for every Keeper bot submission — discoveries unlinkable to submitter, missing from leaderboards/My Profile. → [discoveries.py:218](Haven-UI/backend/routes/discoveries.py)

#### MEDIUM
- `save_system` drops `space_station.orbitalRadius` and `space_station.slot` — Wizard sends them but no schema column exists. → [control_room_api.py:2902-2913](Haven-UI/backend/control_room_api.py)
- `/api/extraction` planet_entry drops 16+ fields the planets table supports (fauna_count, flora_count, has_water, all hazard_*, weather_text, sentinels_text, all wonders fields). → [approvals.py:3449-3487](Haven-UI/backend/routes/approvals.py)
- `submit_system` never validates galaxy name; bad galaxy strings persist verbatim (history of `Galaxy_N` bug class). → [approvals.py:482](Haven-UI/backend/routes/approvals.py)
- `approve_system` UPDATE on edit silently doesn't update `game_mode` — Normal→Permadeath difficulty change frozen forever. → [approvals.py:1398-1442](Haven-UI/backend/routes/approvals.py)
- system-DELETE handler doesn't clean `space_stations` rows — orphans permanently with FKs off. → [control_room_api.py:2316-2323](Haven-UI/backend/control_room_api.py)
- `batch_approve_systems` INSERT missing `game_version` + `expedition_id` columns vs single approve. → [approvals.py:2603-2607](Haven-UI/backend/routes/approvals.py)
- CSV import planet INSERT lists 21 columns vs save_system's 55 — drops biome, weather, sentinel, fauna, flora, biome_subtype, planet_size, hazards, wonders. → [csv_import.py:656-671](Haven-UI/backend/routes/csv_import.py)
- `pending_systems.system_region` column re-purposed as galaxy storage — both `system_region` and `galaxy` get the same value. → [approvals.py:617, 626-627](Haven-UI/backend/routes/approvals.py)

#### LOW
- `/api/discoveries` duplicate check unscoped — two communities can't have same-named discovery in same location. → [discoveries.py:144-160](Haven-UI/backend/routes/discoveries.py)
- Two adjacent INSERT INTO moons paths in approvals.py (~80 dup lines). → [approvals.py:1704-1816](Haven-UI/backend/routes/approvals.py)
- `reject_system` / `reject_discovery` don't delete staged photos from `/haven-ui-photos/` — accumulates storage on Pi.

---

### 3. APPROVALS, AUDIT, EDIT, BATCH

#### CRITICAL
- **`/api/pending_edits/*` is half-implemented** — `approve_edit_request` marks the row `status='approved'` and returns success but does NOT apply the edit (the comment admits it). Neither approve nor reject writes to `approval_audit_log` or activity log. `reviewed_by` hard-coded to literal string `'super_admin'`. UI lies to partners. → [partners.py:995-1061](Haven-UI/backend/routes/partners.py)
- **`/api/reject_region_names/batch` has no self-rejection check and accepts empty reason** — sub-admin can mass-reject any region name (including own) with empty string. The batch approve sibling has both checks. → [control_room_api.py:1999-2088](Haven-UI/backend/control_room_api.py)
- **Single-approve and single-reject region name endpoints have no self-approval/self-rejection prevention** — sub-admin submits region name and approves their own via per-id button. The batch endpoint has the check. → [regions.py:1325-1435, 1438-1514](Haven-UI/backend/routes/regions.py)
- **`GET /api/pending_systems/{id}` and `GET /api/pending_discoveries/{id}` have no community scoping** — partner from civ A can iterate IDs and read civ B's full submission. List endpoint scopes correctly; detail leaks. → [approvals.py:976](Haven-UI/backend/routes/approvals.py), [discoveries.py:867](Haven-UI/backend/routes/discoveries.py)

#### HIGH
- **`PUT /api/pending_systems/{id}` (super-admin edit) doesn't validate `discoveries_draft`** — could re-introduce drafts inside `system_data` JSON that won't be promoted on approval. Silent v1.64 regression vector. → [approvals.py:1023-1109](Haven-UI/backend/routes/approvals.py)
- **Pending count endpoint omits `pending_discoveries` entirely** — Navbar pending badge undercounts when only discoveries are pending. → [approvals.py:880-973](Haven-UI/backend/routes/approvals.py)
- **Audit log INSERTs and exports omit `submission_type`/`search`/`source` filters** — exporting filtered view by source silently exports the entire unfiltered set. → [partners.py:858-924](Haven-UI/backend/routes/partners.py), [ApprovalAudit.jsx:92-130](Haven-UI/src/pages/ApprovalAudit.jsx)
- **Audit export has no `limit` cap** — list endpoint clamps ≤500 (v1.51 Stage 2), export runs unbounded SELECT and OOMs the Pi. → [partners.py:858-924](Haven-UI/backend/routes/partners.py)
- **`batch_jobs` table grows unbounded** — never cleaned up. Slows polling endpoint over time. → [approvals.py:2280-2330](Haven-UI/backend/routes/approvals.py)
- **`GET /api/batch_jobs/{job_id}` has no ownership check** — any admin can poll any job_id and read failures JSON. → [approvals.py:2982-3019](Haven-UI/backend/routes/approvals.py)
- **`reject_discovery` self-check inconsistent with `approve_discovery`** — reject rolled its own inline check that omits `personal_discord_username` and never compares `profile_id`. → [discoveries.py:1086-1105](Haven-UI/backend/routes/discoveries.py)

#### MEDIUM
- Co-submitted discoveries panel doesn't pre-warn when planet/moon names won't resolve — has the data on screen, doesn't compare. → [SystemApprovalTab.jsx:2073-2140](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)
- Batch approval polling has no on-disconnect resume — page reload kills progress UI; backend keeps running silently. → [SystemApprovalTab.jsx:470-550](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)
- Batch approve `batchResults.approved` is fake synthetic placeholder objects — "System 1, System 2" not real names. → [SystemApprovalTab.jsx:526-538](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)
- Pending count region count is unscoped — partner with 2 regions sees badge "52 pending" because all communities' regions counted. → [approvals.py:961-966](Haven-UI/backend/routes/approvals.py)
- `_promote_draft_discoveries` audit insert hard-codes `approver_discord_tag = None` — can't show which leader auto-approved. → [approvals.py:329](Haven-UI/backend/routes/approvals.py)
- `batch_approve_systems` UPDATE missing `game_version` / `expedition_id` columns vs single approve. → [approvals.py:2546-2585](Haven-UI/backend/routes/approvals.py)
- PendingApprovals doesn't refresh DiscordTags filter list after a community is added. → [PendingApprovals.jsx:138-144](Haven-UI/src/pages/PendingApprovals.jsx)

#### LOW
- `approve_discovery` audit insert missing `notes` column for consistency.
- `approve_discovery` / `reject_discovery` activity-log calls inline (blocking) — system paths use BackgroundTasks since v1.55.
- Stale `is_haven_sub_admin` reads in pending_systems list/count/detail — should fully migrate to `civ_scope_filter`.
- Edit-pending PUT doesn't recalculate completeness score after the edit.

---

### 4. BROWSE PATHS, FILTERS, SEARCH, DETAIL PAGES

#### CRITICAL
- **SystemDetail never displays `game_mode` badge** — v1.45.0 changelog says it does; zero references to `game_mode` in the file. Backend returns it; frontend silently drops. → [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx)
- **SystemDetail never displays `completeness_breakdown` panel** — v1.34.0 changelog promises 7-category bar block; backend computes and returns; frontend never reads. Only the rolled-up % shows. → [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx)
- **SystemDetail does not render `space_station` info** — backend returns parsed station data including race, trade goods, prices; frontend has zero reference. → [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx)
- **SystemDetail does not render system discoveries** — discoveries are linked to systems since v1.33; SystemDetail never queries or shows them. Users have no way to see what's been discovered without round-tripping through the Discoveries hub. → [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx)

#### HIGH
- **RegionDetail ignores `reality` + `galaxy` → wrong data on multi-galaxy regions** — calls `/api/regions/.../systems` with no scope params. Per v1.49.0 the regions key is 5-tuple. Hilbert/Calypso/Eissentam regions deep-linked from RegionBrowser silently get the Euclid name and Euclid system list. → [RegionDetail.jsx:198-223](Haven-UI/src/pages/RegionDetail.jsx)
- **`/api/regions/.../systems` backend ignores reality+galaxy entirely** — same coord triple in different realities mixed into one list. → [regions.py:616-703](Haven-UI/backend/routes/regions.py)
- **SystemDetail "Show on Map" button links to non-existent route `/map?focus=...`** — there is no `/map` SPA route. Click navigates to 404. Should be `/map/latest` or `/map/system/{id}`. → [SystemDetail.jsx:522](Haven-UI/src/pages/SystemDetail.jsx)
- **Discoveries quick-search routes to wrong type and uses full reload** — `window.location.href = '/discoveries/other?q=...'` hardcoded "other" type. Searching "fauna name" yields nothing. → [Discoveries.jsx:65-71](Haven-UI/src/pages/Discoveries.jsx)
- **`/api/discoveries/browse` has no q-length guard** — v1.51 added 2-char minimum to old endpoint; the newer browse endpoint that powers `/discoveries/:type` doesn't have it. Single-char wildcard scan reintroduced. → [discoveries.py:319-322](Haven-UI/backend/routes/discoveries.py)
- **`adjectiveColors.js` is exported but never imported anywhere** — v1.37.1 changelog promises tier-color coding; functions are dead. → [adjectiveColors.js](Haven-UI/src/utils/adjectiveColors.js)
- **`is_stub` badge missing on system list and detail views** — only rendered in DiscoveryCard / DiscoveryDetailModal. Browsing /systems shows stub systems indistinguishably from full ones. → [SystemsList.jsx](Haven-UI/src/components/SystemsList.jsx), [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx)
- **Pagination state not URL-synced** — `page` only in `useState`. Bookmarking page 5 of region systems loses the page; refresh resets to 1. → [SystemsList.jsx:52](Haven-UI/src/components/SystemsList.jsx), [RegionBrowser.jsx:65](Haven-UI/src/components/RegionBrowser.jsx), [RegionDetail.jsx:132](Haven-UI/src/pages/RegionDetail.jsx)

#### MEDIUM
- DBStats partner branch drops `populated_regions` and uses different keys vs super-admin/public branches. → [control_room_api.py:3148-3218](Haven-UI/backend/control_room_api.py)
- DBStats partner branch (when fixed) easy to repeat v1.51.1 pre-fix bug — must DISTINCT on 5 keys not 3.
- DBStats public branch returns `unique_galaxies` aliased twice — frontend renders two identical cards. → [control_room_api.py:3260-3261](Haven-UI/backend/control_room_api.py)
- adjectiveColors tier sets miss live values — fauna "Plentiful"/"Vibrant", sentinel "Standard"/"Patrolling"/"Brutal" all fall through to default gray. → [adjectiveColors.js](Haven-UI/src/utils/adjectiveColors.js)
- `/api/galaxies/summary` doesn't SELECT `reality` per row — GalaxyCard always renders "Normal" pill even on Permadeath grid. → [systems.py:459-476](Haven-UI/backend/routes/systems.py)
- AdvancedFilters EMPTY_FILTERS missing `reality`/`galaxy`/`discord_tag` keys — defensive only, fragile contract. → [AdvancedFilters.jsx:24-39](Haven-UI/src/components/AdvancedFilters.jsx)

#### LOW
- No `/discoveries/:type/:id` deep-link route — modal opens from in-page state only.
- `regions/grouped` `system_id_to_key` overwrites silently on duplicate.
- AdvancedFilters dropdown options don't refresh on filter changes — biome=Lush still shows all-biome resources.
- SystemsList sort is client-side only; backend ignores `sort`/`dir`. Sort only re-orders one page.
- RegionBrowser sort similarly only reorders one page.
- Star color hex map missing legacy values like `Unknown(N)` / `White` — falls back to yellow silently.
- SystemDetail completeness "secondary" defaults to "WIP" — 99% S-grade reads "WIP" contradicting the badge.

---

### 5. ADMIN HUBS, COMMUNITY, ANALYTICS, WAR ROOM

#### CRITICAL
- **Partner can grant features beyond own `enabled_features` via `PUT /api/admin/profiles/{id}`** — legacy `PUT /api/sub_admins/{id}` validates parent feature subset; new endpoint doesn't. Partner self-elevates sub-admins to CSV import / war room / batch approvals. → [profiles.py:972-1070](Haven-UI/backend/routes/profiles.py)
- **`/api/discord_tag_colors` reads from `partner_accounts`** — flagged in project memory as known follow-up, still unfixed. New civs get NO color anywhere (region overlays, OG posters, theme tinting). → [partners.py:1203-1237](Haven-UI/backend/routes/partners.py)

#### HIGH
- **`PUT /api/partner/region_color` writes to `partner_accounts`, civ list reads `civilizations`** — partner saves color, never appears on civ card / 3D map / posters. → [partners.py:1133-1170](Haven-UI/backend/routes/partners.py)
- **Audit log Source filter dropdown lists "Companion App" but value is dead** — folded into `haven_extractor` in v1.49.0. Selects nothing. Missing `keeper_bot` option. → [ApprovalAudit.jsx:357-361](Haven-UI/src/pages/ApprovalAudit.jsx)
- **No DELETE endpoint for civilizations** — only soft-delete via `is_active=False`. Submissions still reference deactivated tags. No way to fully purge. → [civilizations.py](Haven-UI/backend/routes/civilizations.py)
- **Civilization tag uniqueness check is case-sensitive** — `"GHUB"` and `"ghub"` allowed simultaneously. Submissions split across casing. → [civilizations.py:234](Haven-UI/backend/routes/civilizations.py)
- **Civilization edit accepts no `tag` field** — typos at founding (`HRC` vs `HRCC`) require DB surgery to fix. No bulk-rename path. → [civilizations.py:281-285](Haven-UI/backend/routes/civilizations.py)
- **Profile.jsx default-civ dropdown reads `/api/communities` (excludes Personal)** — hardcodes "Personal" lowercase at end vs `/api/discord_tags` returning canonical "Personal" first. Casing mismatch with normalizer. → [Profile.jsx:43, 184-196](Haven-UI/src/pages/Profile.jsx)

#### MEDIUM
- Sub-admin update via legacy `PUT /api/sub_admins/{id}` doesn't audit-log permission changes (used by SubAdminManagement.jsx). New endpoint does. → [partners.py:468-561](Haven-UI/backend/routes/partners.py)
- Reissue extractor key audit row uses approver_account_id from profile_id — NULL for legacy super_admin sessions. → [extractor.py:540, 550](Haven-UI/backend/routes/extractor.py)
- `/api/communities` no ETag — extractor mod cache stays stale, submits to deactivated tags silently.
- WarRoom enrollment writes to `partner_accounts.enabled_features` — civs created post-v1.80.0 have no legacy partner_accounts row, war-room tab won't show. → [warroom.py:441](Haven-UI/backend/routes/warroom.py)
- PartnerAnalytics fires 6 simultaneous queries per filter change — no client cache. Heavy admin can briefly OOM Pi. discoveries table missing `(discord_tag, submission_timestamp DESC)` composite. → [PartnerAnalytics.jsx:130-143](Haven-UI/src/pages/PartnerAnalytics.jsx)
- AnalyticsHub Overview tab description says "Submissions + discoveries combined" for everyone — partners think they see global stats. → [AnalyticsHub.jsx:100](Haven-UI/src/pages/AnalyticsHub.jsx)
- AccessControl partner can see "Toggle Active" / "Reset Password" buttons that 403 on click — confusing UX. → [AccessControl.jsx:37, 57](Haven-UI/src/pages/AccessControl.jsx)
- Existing legacy `discord_tag` values in systems differ in casing from `civilizations.tag` — case-sensitive filters silently exclude them.

#### LOW
- AdminTools placeholder mentions WAL checkpoint / VACUUM / health endpoints exist but UI doesn't surface them.
- Settings.jsx still has dead `doBackup` / `migrateHubTags` handlers and `migrating` state — changelog claims they were removed.
- CivilizationManagement member-add modal hardcodes "fuzzy match not enabled in this UI" — `/api/profiles/lookup` does return suggestions; UI throws them away.
- Audit log filter UI doesn't expose `keeper_bot` source value.
- CommunityDetail no civ-not-found 404 for typo civ tag.
- `'all' not in parent_features` check in sub-admin endpoint is dead — no code grants the literal `"all"` string.

---

### 6. MOBILE RESPONSIVE, NAVBAR, ROUTING, VISUAL POLISH

#### HIGH
- **`SearchableSelect` dropdown forces `minWidth: '280px'`** — overflows narrow form columns on phone. Used in Wizard PlanetEditor/MoonEditor (200px columns), Profile, Discovery submit. Dropdown clips/overlays adjacent fields and right edge of viewport. → [SearchableSelect.jsx:46-55](Haven-UI/src/components/SearchableSelect.jsx) — **Fix:** `minWidth: 'min(280px, 90vw)'`
- **CSV Import column-mapping rows force `min-w-[160px]` inside flex row with no wrap** — at 360px phone, the select gets pushed offscreen with no `overflow-x-auto`. → [CsvImport.jsx:239-256](Haven-UI/src/pages/CsvImport.jsx) — **Fix:** add `flex-wrap` + `min-w-0 sm:min-w-[160px]`
- **WarRoom war-goal grid `grid-cols-5` with no breakpoints** — 5 buttons per row at 360px = 70px each, text-[10px] truncated unreadable. → [WarRoom.jsx:827](Haven-UI/src/pages/WarRoom.jsx) — **Fix:** `grid-cols-2 sm:grid-cols-3 md:grid-cols-5`
- **WarRoom command tab header action button row has no wrap** — DECLARE WAR + Claim Territory + News + HQ + bell + Logout chain pushes rightmost buttons offscreen on phone. → [WarRoom.jsx:3262-3382](Haven-UI/src/pages/WarRoom.jsx)
- **WarMap3D drill-down panel hard-pinned at `right-3 bottom-3 w-80`** — covers 89% of phone width with no escape. → [WarMap3D.jsx:709](Haven-UI/src/components/WarMap3D.jsx) — **Fix:** `inset-x-3 sm:inset-x-auto sm:right-3 w-auto sm:w-80`
- **WarRoom DECLARE WAR modal has no padding on backdrop and traps inner scroll** — uses `flex items-center justify-center` (no `p-2`), inner uses `flex-1 overflow-hidden flex flex-col`. Modal touches both edges on phone. → [WarRoom.jsx:802-870](Haven-UI/src/pages/WarRoom.jsx) — **Fix:** adopt shared `Modal.jsx` pattern.

#### MEDIUM
- PartnerAnalytics filter row stacks 4-5 wide controls awkwardly; DateRangePicker takes full row pushing selects below. → [PartnerAnalytics.jsx:240-293](Haven-UI/src/pages/PartnerAnalytics.jsx)
- ApprovalAudit table desktop layout has hardcoded fixed columns totaling ~880px; tablet (768-880px) horizontal-scrolls. Mobile card layout via `md:hidden` exists; tablet sits in dead zone — change to `lg:hidden`. → [ApprovalAudit.jsx:288, 487-498](Haven-UI/src/pages/ApprovalAudit.jsx)
- CommunityStats contributor tables on `lg:grid-cols-2` get cramped at typical laptop widths; tag chips wrap onto 2-3 lines. → [CommunityStats.jsx:322](Haven-UI/src/pages/CommunityStats.jsx)
- PendingApprovals review modal capped at `lg:max-w-3xl`; dense planet/moon grids cramped on tablet. → [SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)
- Wizard glyph picker uses `grid-cols-4` on phone with `text-[10px]` labels — labels hard to read.
- Hub pages use `-mx-6 -mt-6` but container has `padding-left: 18px` on phone — over-pulls and causes horizontal scroll. → [AnalyticsHub.jsx:51, AccessControl.jsx:60, AdminTools.jsx:80](Haven-UI/src/pages/) — **Fix:** `-mx-3 sm:-mx-6 -mt-3 sm:-mt-6`

#### LOW
- Navbar mobile menu has no `max-h` / scroll — super admin's 14+ rows extend past viewport, must use page scroll.
- CivilizationManagement card stats `grid-cols-3` with 4-digit values wrap.
- Wizard advanced flow section-pill mobile nav has no scroll-affordance fade/chevron.
- Changelog page `text-5xl md:text-6xl` h1 — verify doesn't overflow at 320px width.
- Profile submissions tab — verify 4-digit count badges don't push tabs past viewport.
- Many `text-xs px-3 py-1.5` action buttons (~28px tall) below 44px touch target on phone.

#### POLISH
- `CelestialBodyEditor` template literal `gap-${X}` won't be picked up by Tailwind JIT — falls back to no gap. → [CelestialBodyEditor.jsx:108](Haven-UI/src/components/CelestialBodyEditor.jsx)

---

## Suggested triage order

**Phase 1 — Security / data integrity / silent loss (do first):**
- Items 1-10 from "Top 10 to fix first" above
- Plus: Audit export missing filters and uncapped (HIGH × 2 in Approvals) — compliance-relevant

**Phase 2 — Self-approval prevention pattern cleanup:**
- Drop `'partner'` from exempt list in `check_self_submission()`
- Add `check_self_submission()` to region single-approve, region single-reject, region batch-reject
- Replace inline check in `reject_discovery` with the canonical helper

**Phase 3 — Frontend feature gaps the changelog claims are shipped:**
- SystemDetail: game_mode badge, completeness_breakdown panel, space_station card, system discoveries list
- adjectiveColors.js: import in SystemDetail (file is dead code)
- is_stub badge in SystemsList + SystemDetail
- Show on Map button → `/map/latest` not `/map`
- RegionDetail: thread reality+galaxy through URL/queries

**Phase 4 — DB column drift cleanup (one pass to fix all):**
- Add `glyph_code` to `submit_system` INSERT (Phase 1 already lists this)
- Sync `save_system` planets/moons INSERT column lists with approve_system (canonical)
- Add `game_mode` to `save_system` and `submit_system` INSERTs
- Add `game_version` + `expedition_id` to `batch_approve` UPDATE
- Add space_stations DELETE to approve_system edit branch and DELETE handler
- Enable `PRAGMA foreign_keys = ON` (single change, covers most orphan-row classes going forward)

**Phase 5 — Civ source consolidation (legacy partner_accounts → civilizations):**
- `/api/discord_tag_colors` — rewrite to read from `civilizations.region_color`
- `PUT /api/partner/region_color` — write to `civilizations.region_color`
- WarRoom enrollment — migrate to civilizations key
- Settings region color save target

**Phase 6 — Mobile responsive batch:**
- Items from §6 above; mostly Tailwind class string changes
- Quick wins (highest leverage): SearchableSelect minWidth, hub pages negative margin, WarRoom war-goal grid, CSV Import flex-wrap, WarMap3D bottom-sheet, navbar mobile max-h

**Phase 7 — Polish / dead code / housekeeping:**
- LOW-severity items
- batch_jobs cleanup task
- Settings.jsx dead handler removal
