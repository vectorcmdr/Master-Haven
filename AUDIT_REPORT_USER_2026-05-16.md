# Master Haven — End-User Audit (Public + Member)
**Date:** 2026-05-16
**Scope:** Public visitor (not logged in) + Member (tier 4/5) UX
**Angle:** Migration archaeology (civs-vs-partner_accounts drift) + UX walkthrough
**Method:** 4 parallel agents (public browse · discoveries/community/region · member profile/submit · cross-cutting drift)
**Type:** Read-only audit — no code changes made

---

## TL;DR

**~85 unique findings after dedup.** The biggest finding is not any single bug — it's that the **`civilizations` migration is genuinely half-done in the UI**. The data layer flipped to canonical civs in v1.80.0, but ~9 frontend pages, multiple modal copy strings, several React component constants, three backend analytics endpoints, and the entire `tagColors.js` hardcoded list never followed. That's the "unwanted functionality" Parker felt — it's everywhere.

| Severity | Count | Meaning |
|---|---|---|
| BROKEN / STALE-CRITICAL | 16 | Feature literally produces wrong data or doesn't work for the user |
| CONFUSING | 38 | User is misled, terminology contradicts itself, or workflow has unexplained dead ends |
| STALE | 14 | Pre-migration UI/copy that's just sitting there |
| POLISH | 17 | Minor visual / copy fixes |

### The 7 themes that explain ~70% of findings

If you fix the **patterns** instead of the **instances**, the audit list collapses fast.

#### Theme 1 — "Partner" vocabulary never migrated to "Civilization" in the UI

Touches: Settings (3 sections still labeled "Partner"), AdminLoginModal (tab labeled "Admin / Partner"), TIER_LABELS const in Profile + UserManagement (tier 2 = "Partner"), `PARTNER_FEATURES` const, PendingApprovals copy ("partner edits", "partner: username"), SubAdminManagement copy ("partner discords"), PartnerAnalytics page header, ApiKeys copy, AccessControl docstring, **dead `PartnerManagement.jsx` file still in the bundle** even though its route is aliased to CivilizationManagement.

→ Fix once: pick a canonical user-facing term ("Civilization Leader" for tier 2, "Civilization" for the entity), grep-replace across `src/`, delete `PartnerManagement.jsx`.

#### Theme 2 — `keeper_bot` source isn't first-class anywhere

After v1.69.0 there are three sources (`manual` / `haven_extractor` / `keeper_bot`) but the UI still works in a 2-source world:
- PendingApprovals modal shows literal text `keeper_bot` instead of a labeled pill
- Profile.jsx "My Submissions" tabs are only "All / Manual / Extractor" (Keeper rows get bucketed as manual via fallthrough)
- `/api/public/activity-timeline` returns Manual + Extractor + Discoveries series — Keeper systems invisible on the public stats chart
- `/api/analytics/source-breakdown` `ELSE` arm groups `keeper_bot` into `manual`
- CommunityStats upload-method bar math: `manualPct + extractorPct = 100` — silently wrong when keeper rows exist

→ Fix once: backend CASE statements get a third arm; frontend grows a third tab + a third bar segment.

#### Theme 3 — "Personal" bucket: case-sensitivity + write-side normalizer never finished

v1.63 fixed the public-overview READ path to collapse `NULL`/`''`/`'personal'`/`'Personal'` into one bucket. But:
- `/api/public/community-regions` filters by raw `discord_tag` — Personal drill-down returns 0 systems
- `/api/public/contributors` same bug — per-civ-Personal leaderboard undercounts
- Profile dropdown writes capital "Personal" via `/api/discord_tags`, but Wizard hardcodes lowercase `'personal'` in conditionals — value mismatch, downstream comparisons silently miss
- Wizard discord_tag dropdown shows "Personal" twice (once from API, once hardcoded fallback)
- Profile lets a user set "Personal" as their `default_civ_tag` — semantically nonsensical, then fires the personal-handle modal on every Wizard load
- Frontend `=== 'personal'` checks are exact-match in 6+ files — won't match if `'Personal'` (capital) ever flows in

→ Fix once: backend normalizer enforced on WRITE not just READ; frontend `isPersonalTag()` helper used everywhere; drop "Personal" from `default_civ_tag` dropdown.

#### Theme 4 — `discord_tag` vs `display_name` shown inconsistently

The Wizard shows "Haven Royal Cartography Corps (HRCC)" in the picker. Every other surface shows just "HRCC". `/community-stats/HRCC` URL uses tag; page header uses display_name; breadcrumbs use neither. `DiscordTagBadge` only renders the tag. Profile's "Default Community" line shows the raw tag, not the friendly name.

→ Fix once: pass both to `DiscordTagBadge`, render `display_name` as primary with `tag` as tooltip/sub-line. Same component everywhere.

#### Theme 5 — Public Dashboard is leftover admin UI from before the landing page

After clicking through the cinematic landing page, the first thing a public visitor sees is:
- Page header "Haven Control Room" (admin terminology)
- "Add New System" CTA button (no login wall, no context)
- "Pending Review" card showing internal admin counts
- "Quick Actions" linking to `/pending-approvals` (which 404s for non-admin)

→ Fix: gate the admin-flavored sections behind `isAdmin`; replace with public-friendly content (recent discoveries, featured systems, community spotlight).

#### Theme 6 — Wizard treats logged-in members as if they were anonymous

- "Your Discord Username" field still rendered + required, even though the session already knows
- Submitting writes `personal_discord_username` UNCONDITIONALLY (even when the user picked a real civ like GHUB) — pollutes the column intended for the Personal path only
- "Personal community" modal pops every time a member with `default_civ_tag='personal'` opens the Wizard, even though their username is already in session
- "Discord Community (Required)" red border flashes on initial render because pre-fill is in a useEffect that runs after first paint

→ Fix: when `user` is set, treat identity as session-derived; don't ask for fields you already have; don't pop modals to confirm what you already know.

#### Theme 7 — `tagColors.js` hardcoded list never migrated to `civilizations.region_color`

Hardcoded list: Haven, IEA, B.E.S, ARCH, TBH, EVRN, Personal. Every other civ (HRCC and the 30+ active civs created post-v1.80.0) falls through to either an unstable hash palette OR a generic `bg-indigo-500`. `DiscordTagBadge.jsx` doesn't consult the API color cache before falling through. The `/api/discord_tag_colors` fix yesterday wired the SOURCE; the COMPONENT still ignores it.

→ Fix once: `DiscordTagBadge` reads from `getTagColorFromAPI(tag)` first, hash-palette fallback only if API returns nothing. Delete the hardcoded list.

---

## Top 10 things to fix first (impact-weighted)

1. **BROKEN — Navbar pending badge always reads 0** — key mismatch. Dashboard fetches `{systems, regions}`, navbar reads `.count` which doesn't exist. Admins literally cannot see the pending count in nav. → [Navbar.jsx:69-72](Haven-UI/src/components/Navbar.jsx)
2. **BROKEN — Public Dashboard hero is admin UI** — public visitor first impression after landing CTA is "Haven Control Room" + "Add New System" + "Pending Review" card. Gate behind `isAdmin`. → [Dashboard.jsx:185-187, 239-248, 293-358](Haven-UI/src/pages/Dashboard.jsx)
3. **BROKEN — Wizard pollutes `personal_discord_username` for non-personal submissions** — logged-in member submitting to GHUB still has their session username written into `personal_discord_username`. Every member submission gets polluted. → [Wizard.jsx:606-611, 748](Haven-UI/src/pages/Wizard.jsx)
4. **BROKEN — Personal-bucket drill-down on `/community-stats/Personal` is empty** — backend `community-regions` and `contributors` endpoints filter by raw `discord_tag`, missing every NULL/`''`/lowercase `personal` row. → [analytics.py:1318-1437, 1551-1617](Haven-UI/backend/routes/analytics.py)
5. **STALE-CRITICAL — keeper_bot invisible across the analytics surface** — public timeline chart, source-breakdown, Profile tabs, PendingApprovals modal all miss it. Keeper systems silently bucket as manual. → analytics.py + 4 frontend files
6. **BROKEN — Tier-5 readonly members can edit systems via the "Full edit (Wizard)" link** — Wizard has no readonly gate. Submission lands in pending; member never warned their account is readonly. → [SystemDetail.jsx:469-474](Haven-UI/src/pages/SystemDetail.jsx) and Wizard.jsx
7. **BROKEN — Member login response misses `civ_memberships` / `civ_tags` / `account_id`** — same Phase-1 finding shape as sub-admin login had. Members can't see the "Acting as" picker until next page reload. → [profiles.py:314-326](Haven-UI/backend/routes/profiles.py)
8. **BROKEN — DiscoveryType "All Discoveries" empty/loading copy is grammatically broken** — "No all discoveries found" / "Be the first to submit a all discoveries discovery!". Also the Discoveries hub's "View all →" link still points to dead `/discoveries/other` instead of `/discoveries/all`. → [DiscoveryType.jsx:167, 173, 177](Haven-UI/src/pages/DiscoveryType.jsx) + [Discoveries.jsx:175](Haven-UI/src/pages/Discoveries.jsx)
9. **BROKEN — URLBar "From Map" stub button shown in production** — code comment self-identifies as "Phase 3 stub". Click does nothing visible. → [URLBar.jsx:37-44](Haven-UI/src/components/URLBar.jsx)
10. **BROKEN — DiscoverySubmitModal is orphan dead code** — file exists, no button anywhere opens it. Members have NO path to submit a discovery against an existing system from the Discoveries page; only via Wizard (which requires also re-entering the whole system). → [DiscoverySubmitModal.jsx](Haven-UI/src/components/DiscoverySubmitModal.jsx)

---

## Findings by user surface

### Public landing → Dashboard → Browse

- **BROKEN** Navbar pending count badge always 0 (key mismatch) — [Navbar.jsx:69-72](Haven-UI/src/components/Navbar.jsx)
- **BROKEN** URLBar "From Map" production-shipped stub — [URLBar.jsx:37-44](Haven-UI/src/components/URLBar.jsx)
- **BROKEN** Dashboard hero "Haven Control Room" + admin CTA visible to public — [Dashboard.jsx:185, 239](Haven-UI/src/pages/Dashboard.jsx)
- **BROKEN** Dashboard "Pending Review" card visible to public, click → / (route guard rebounds) — [Dashboard.jsx:293-337](Haven-UI/src/pages/Dashboard.jsx)
- **BROKEN** Dashboard Quick Actions exposes admin links to public — [Dashboard.jsx:339-358](Haven-UI/src/pages/Dashboard.jsx)
- **BROKEN** Galaxy poster fallback leaves empty top-half of card for non-Euclid galaxies — [GalaxyGrid.jsx:166-173](Haven-UI/src/components/GalaxyGrid.jsx)
- **CONFUSING** Conflict color uses grade-tier palette: Medium conflict = gold (best) — semantic inversion — [SystemDetail.jsx:386-392](Haven-UI/src/pages/SystemDetail.jsx)
- **CONFUSING** System detail "Community" card for personal submissions just says "Personal submission" with no contributor name/link — [SystemDetail.jsx:436-445](Haven-UI/src/pages/SystemDetail.jsx)
- **CONFUSING** Stat tiles duplicate hero-pill data with value/secondary swapped (Economy: value=T2 / secondary=Mining vs. hero pill "Mining T2") — [SystemDetail.jsx:384-399](Haven-UI/src/pages/SystemDetail.jsx)
- **CONFUSING** Sea of Gidzenuf hard-pinned first in region sort with no UI explanation — [RegionBrowser.jsx:11-14](Haven-UI/src/components/RegionBrowser.jsx)
- **CONFUSING** Region sort options "Named first" / "Name A-Z" / "System count" — only first works; others silently only re-sort visible page — [RegionBrowser.jsx:11-14, 95-103](Haven-UI/src/components/RegionBrowser.jsx)
- **STALE** "Edit" button on SystemDetail visible to public visitors; clicking + saving silently queues a pending edit with no attribution — [SystemDetail.jsx:359-362](Haven-UI/src/pages/SystemDetail.jsx)
- **STALE** SystemDetail caption "discovered by X" not linked to `/voyager/X` — [SystemDetail.jsx:375-379](Haven-UI/src/pages/SystemDetail.jsx)
- **STALE** DBStats: "Active Communities" stat hidden from public; CommunityStats and DBStats give different civ pictures — [DBStats.jsx:38-48](Haven-UI/src/pages/DBStats.jsx)
- **STALE** DBStats `customLabels` only renames 3 keys; rest are raw snake_case ("Total Planet Pois") — [DBStats.jsx:30-34](Haven-UI/src/pages/DBStats.jsx)
- **STALE** Landing page footer hardcodes "Haven v1.57" — 7 minor versions out of date — [landing/index.html:363](Haven-UI/landing/index.html)
- **POLISH** Star pill renders "Unknown" as a literal label instead of suppressing or "?" — [SystemsList.jsx:235-242](Haven-UI/src/components/SystemsList.jsx)
- **POLISH** Dashboard daily-changes only handles `> 0` case; negative collapses to "— 24h" with no down-arrow — [Dashboard.jsx:224-232](Haven-UI/src/pages/Dashboard.jsx)
- **POLISH** No page-size selector or jump-to-page on region pagination — [RegionBrowser.jsx:335-360](Haven-UI/src/components/RegionBrowser.jsx)
- **POLISH** Landing-page "Create" CTA drops anonymous into Wizard with zero onboarding context — [landing/index.html:312-326](Haven-UI/landing/index.html)
- **POLISH** URLBar hardcodes "havenmap.online" origin even in dev — [URLBar.jsx:18](Haven-UI/src/components/URLBar.jsx)
- **POLISH** Breadcrumb home label "Systems" duplicates page header & route name — [BreadcrumbBar.jsx:60](Haven-UI/src/components/BreadcrumbBar.jsx)
- **POLISH** Dashboard "Top Regions" purple = hasCustomName color code with no legend — [Dashboard.jsx:387-389](Haven-UI/src/pages/Dashboard.jsx)

### Discoveries hub + community + region (public)

- **BROKEN** DiscoveryType "all" empty + loading copy grammatically broken ("No all discoveries found") — [DiscoveryType.jsx:167, 173, 177](Haven-UI/src/pages/DiscoveryType.jsx)
- **BROKEN** Discoveries hub "View all →" still points at dead `/discoveries/other` — [Discoveries.jsx:175](Haven-UI/src/pages/Discoveries.jsx)
- **BROKEN** `/api/public/community-regions` returns 0 systems for Personal bucket (raw discord_tag filter, no normalizer) — [analytics.py:1551-1617](Haven-UI/backend/routes/analytics.py)
- **BROKEN** `/api/public/contributors` same Personal-bucket undercount — [analytics.py:1318-1437](Haven-UI/backend/routes/analytics.py)
- **STALE** CommunityStats "Communities" count mixes civilizations + Personal + orphans under one label — [CommunityStats.jsx:117](Haven-UI/src/pages/CommunityStats.jsx)
- **STALE** CommunityDetail "Members" stat is actually `unique_contributors` from systems table — civ with 50 Discord members + 3 submitters shows "3 Members" — [CommunityDetail.jsx:108](Haven-UI/src/pages/CommunityDetail.jsx)
- **STALE** DiscordTagBadge on RegionDetail/SystemList uses `tagColors` hardcoded dict — civs not in 7-item list get `bg-indigo-500` generic — [DiscordTagBadge.jsx:27](Haven-UI/src/components/DiscordTagBadge.jsx) + [tagColors.js:19-60](Haven-UI/src/utils/tagColors.js)
- **CONFUSING** RegionDetail "Galaxies" stat tile can show "Euclid, Hilbert" CSV that contradicts URL scope — [RegionDetail.jsx:642-644](Haven-UI/src/pages/RegionDetail.jsx)
- **CONFUSING** RegionDetail silently defaults reality=Normal+galaxy=Euclid on deep links without query params — no banner explains user might be looking at wrong region — [RegionDetail.jsx:131-132](Haven-UI/src/pages/RegionDetail.jsx)
- **CONFUSING** SSR OG region card title always "Region X,Y,Z" — never the actual region name even when one exists — [ssr.py:221-229](Haven-UI/backend/routes/ssr.py)
- **CONFUSING** SSR `og_region` handler ignores ?reality= / ?galaxy= query params; redirect strips them; Discord embed loses scope round-trip — [ssr.py:476-483](Haven-UI/backend/routes/ssr.py)
- **CONFUSING** DiscoveryDetailModal location hierarchy renders dangling `›` when no system_id — [DiscoveryDetailModal.jsx:218-256](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx)
- **CONFUSING** DiscoveryDetailModal "Discovered by" falls back to raw Discord snowflake ID for Keeper rows missing the field — looks like spam — [DiscoveryDetailModal.jsx:283](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx)
- **CONFUSING** DiscoveryDetailModal doesn't show the discoverer's civ tag — inconsistent with system pages — [DiscoveryDetailModal.jsx:280-284](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx)
- **CONFUSING** CommunityDetail typo'd URL renders "page-not-found" as "civ with zero data" — no 404 distinction — [CommunityDetail.jsx:62-63](Haven-UI/src/pages/CommunityDetail.jsx)
- **POLISH** DiscoveryCard location row crams 5 facets in one truncated line — [DiscoveryCard.jsx:100-114](Haven-UI/src/components/discoveries/DiscoveryCard.jsx)
- **POLISH** Changelog timeline JSON file last entry was 2026-04-27 — page lies about freshness — [data/changelog/timeline.json](Haven-UI/src/data/changelog/timeline.json)
- **POLISH** CommunityStats no skeleton loader — phone visitors see blank dark page — [CommunityStats.jsx:92-98](Haven-UI/src/pages/CommunityStats.jsx)
- **POLISH** Docs hub Discord CTA invite URL worth spot-checking (looks 9-char, normal is 8) — [Docs.jsx:119](Haven-UI/src/pages/Docs.jsx)
- **POLISH** DocPage no "Document N of M" indicator — [DocPage.jsx:263-282](Haven-UI/src/pages/DocPage.jsx)
- **POLISH** RegionDetail "Pending name" surfacing doesn't show who proposed it — dead-end fact — [RegionDetail.jsx:577-581](Haven-UI/src/pages/RegionDetail.jsx)

### Member: login, profile, claim flow

- **BROKEN** Member login response missing `civ_memberships` / `civ_tags` / `account_id` etc — "Acting as" chip hidden until next `/api/admin/status` poll — [profiles.py:314-326](Haven-UI/backend/routes/profiles.py)
- **BROKEN** ProfileClaimModal "Create" button silently disabled for 1-3 char passwords with no error message — [ProfileClaimModal.jsx:142](Haven-UI/src/components/ProfileClaimModal.jsx)
- **CONFUSING** AdminLoginModal Member tab error wording sends user on wrong flow ("Submit a system first" but you CAN submit without an existing profile) — [AdminLoginModal.jsx:60, 137](Haven-UI/src/components/AdminLoginModal.jsx)
- **CONFUSING** AdminLoginModal "log in passwordless → set password on Profile page" instruction conflicts with Profile page hiding Edit button until password is set — chicken-and-egg until they spot the promotion banner — [AdminLoginModal.jsx:107-112](Haven-UI/src/components/AdminLoginModal.jsx)
- **CONFUSING** ProfileClaimModal suggestion rows show only username + civ tag — no system count / last-seen to help disambiguate when names are similar — [ProfileClaimModal.jsx:76-91](Haven-UI/src/components/ProfileClaimModal.jsx)
- **STALE** `/api/profiles/me` submission counts JOIN by `discord_tag` even for members — a member with `partner_discord_tag = GHUB` gets credited with EVERY GHUB-tagged system (1200 instead of 20) — [profiles.py:373-394](Haven-UI/backend/routes/profiles.py)
- **STALE** Profile "Member Since" reads `created_at` (=v1.57.0 backfill date for legacy profiles) — actual first submission date is hidden — [Profile.jsx:260-262](Haven-UI/src/pages/Profile.jsx)
- **STALE** Profile.jsx pulls civ list from `/api/discord_tags`, lets user pick "Personal" as default community — semantically wrong, then fires personal-handle modal every Wizard load — [Profile.jsx:43-50, 192-205](Haven-UI/src/pages/Profile.jsx)
- **STALE** No referential integrity between `user_profiles.default_civ_tag` and `civilizations.tag` — civ rename silently breaks profile — [Profile.jsx:48](Haven-UI/src/pages/Profile.jsx)
- **POLISH** Voyager Card section broken-image for members with zero submissions — [Profile.jsx:471, 529-535](Haven-UI/src/pages/Profile.jsx)
- **POLISH** Profile submission pagination resets on tab switch with no indicator — [Profile.jsx:128-131](Haven-UI/src/pages/Profile.jsx)
- **POLISH** Profile pending submissions hidden under non-All tabs — can't filter "extractor only" + see "pending extractor uploads" — [Profile.jsx:315](Haven-UI/src/pages/Profile.jsx)
- **POLISH** CommunityStats contributors link to `/voyager/:username` with normalized slug but no tooltip explaining the `#1234` discriminator stripping — [CommunityStats.jsx:375-377](Haven-UI/src/pages/CommunityStats.jsx)
- **POLISH** Profile pending entries are plain `<div>` not links — can't open to verify what was submitted — [Profile.jsx:319-329](Haven-UI/src/pages/Profile.jsx)
- **POLISH** "Member Since" uses `toLocaleDateString()` raw → US/EU locale split between `5/16/2026` and `16/05/2026` — [Profile.jsx:261](Haven-UI/src/pages/Profile.jsx)

### Member: Wizard / submit / region flows

- **BROKEN** Wizard writes `personal_discord_username` UNCONDITIONALLY for logged-in members, polluting the column even when discord_tag != personal — [Wizard.jsx:606-611, 748](Haven-UI/src/pages/Wizard.jsx)
- **BROKEN** Tier-5 readonly member can edit any system via "Full edit (Wizard)" link with no readonly gate — [SystemDetail.jsx:469-474](Haven-UI/src/pages/SystemDetail.jsx) + Wizard.jsx
- **BROKEN** DiscoverySubmitModal is dead code (orphan) — no button anywhere opens it; members have no Discoveries-page submit path — [DiscoverySubmitModal.jsx](Haven-UI/src/components/DiscoverySubmitModal.jsx)
- **CONFUSING** Wizard "Discord Community" dropdown shows red "Required" border that flashes green on initial render (pre-fill is in useEffect after first paint) — [Wizard.jsx:1907-1937](Haven-UI/src/pages/Wizard.jsx)
- **CONFUSING** Wizard "Personal" community selection fires the personal-handle modal every time even for logged-in member whose username is in session — [Wizard.jsx:1915-1923](Haven-UI/src/pages/Wizard.jsx)
- **CONFUSING** Wizard requires "Your Discord Username" field for logged-in members even though session knows — [Wizard.jsx:543, 1939-1953](Haven-UI/src/pages/Wizard.jsx)
- **CONFUSING** Wizard pre-filled defaults have no "auto-filled from your defaults" annotation — member can't tell what came from profile vs prior session — [Wizard.jsx:282-286](Haven-UI/src/pages/Wizard.jsx)
- **CONFUSING** RegionDetail "Set Name" button shown to readonly members; submission accepts but no "your pending region names" view on Profile — [RegionDetail.jsx:596-612](Haven-UI/src/pages/RegionDetail.jsx)
- **POLISH** CoAuthorChipInput doesn't fuzzy-match against existing profiles — orphan strings can't be linked at approval — [Wizard.jsx:1958-1964](Haven-UI/src/pages/Wizard.jsx)
- **POLISH** DiscoverySubmitModal pre-fills from AuthContext snapshot — stale if user updated profile mid-session — [DiscoverySubmitModal.jsx:133-134](Haven-UI/src/components/DiscoverySubmitModal.jsx)

### Cross-cutting: migration drift + terminology

- **STALE-CRITICAL** PendingApprovals modal still renders `companion_app` source pill (dead since v1.69.0); raw `keeper_bot` text shown as blue pill with no friendly label — [SystemApprovalTab.jsx:908-911, 1493-1498](Haven-UI/src/components/approvals/SystemApprovalTab.jsx) + [ApprovalAudit.jsx:179](Haven-UI/src/pages/ApprovalAudit.jsx) (`getSourceBadge` same problem)
- **STALE-CRITICAL** Profile.jsx "My Submissions" tabs are "All / Manual / Extractor" only — Keeper rows hidden — [Profile.jsx:32, 78, 282-307, 322, 347](Haven-UI/src/pages/Profile.jsx)
- **STALE-CRITICAL** `/api/public/activity-timeline` and `/api/analytics/source-breakdown` drop `keeper_bot` into manual via ELSE arm — public chart lies about submission volume — [analytics.py:538-553, 1461-1511](Haven-UI/backend/routes/analytics.py)
- **CONFUSING** Wizard "personal" dropdown shows "Personal" twice (API row + hardcoded fallback) — [Wizard.jsx:1925-1929](Haven-UI/src/pages/Wizard.jsx)
- **CONFUSING** Frontend `=== 'personal'` exact-match in 6+ files won't catch backend-normalized "Personal" capitalized — [Wizard.jsx, DiscordTagBadge.jsx, PendingApprovals.jsx, RegionThumb.jsx, ApiKeys.jsx, GalaxyAtlas.jsx]
- **CONFUSING** 8 pages still use "Partner" terminology after v1.80.0 made civilizations canonical: Settings (3 sections), Profile TIER_LABELS, UserManagement TIER_LABELS+`PARTNER_FEATURES`, AccessControl docstring, PartnerAnalytics page header, Analytics.jsx, PendingApprovals copy (6 sites), SubAdminManagement (4 sites), AdminLoginModal tab — [grep "Partner" across src/]
- **CONFUSING** Wizard dropdown shows "{display_name} ({tag})" but every other surface shows only `tag` — naming mental-model split — [Wizard.jsx:1927](Haven-UI/src/pages/Wizard.jsx) vs [DiscordTagBadge.jsx:27](Haven-UI/src/components/DiscordTagBadge.jsx)
- **CONFUSING** PendingApprovals "Submitted by: parker_stouffer" prefers `personal_discord_username` over linked `submitter_profile_id` — leaks impression submissions are anonymous strings — [SystemApprovalTab.jsx:921, 1485, 1681](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)
- **CONFUSING** Audit Log only in Governance dropdown — dropdown visibility computed from `showAdminDropdown` not from union of items' visibility, so a partner with only one Governance item visible sees an empty dropdown chevron — [Navbar.jsx:149](Haven-UI/src/components/Navbar.jsx)
- **CONFUSING** AccessControl hub has 4 tabs but the tier-2/3 elevation workflow lives in CivilizationManagement under "Super Admin" dropdown — bifurcated user-management — [AccessControl.jsx:19](Haven-UI/src/pages/AccessControl.jsx)
- **CONFUSING** CivilizationManagement and UserManagement both define their own duplicate `enabled_features` lists — will drift on new feature flags — [CivilizationManagement.jsx:31-40, UserManagement.jsx:9-18]
- **CONFUSING** "Sub-Admin" word means two contradictory things on adjacent pages: civ role vs membership-derived tier — [CivilizationManagement.jsx:28 vs UserManagement.jsx:463-512]
- **CONFUSING** `/community-stats/HRCC` URL uses tag but page header shows display_name; breadcrumbs use neither — [CommunityStats.jsx:134, CommunityDetail.jsx:62, 100]
- **CONFUSING** PendingApprovals copy: "approve the partner's edit" used in modal even though edit requests can come from any tier — [PendingApprovals.jsx:398, 727, 749, 1792, 1796, 1886](Haven-UI/src/pages/PendingApprovals.jsx)
- **CONFUSING** DBStats lists `partner_accounts` row count in Administration bucket but no `civilizations` count — misleading auth-schema picture — [DBStats.jsx:42](Haven-UI/src/pages/DBStats.jsx)
- **CONFUSING** "Member" vs "Voyager" identity terminology split: Navbar says "(Member)", login modal says "Member", Profile says "Voyager Card", route is `/voyager/`, brand is "Voyager's Haven" — same role, 3 names
- **CONFUSING** AdminLoginModal tab "Admin / Partner" conflates tier-1 super admin with tier-2 civ leaders — [AdminLoginModal.jsx:81](Haven-UI/src/components/AdminLoginModal.jsx)
- **STALE** War Room enrollment still keyed on `war_room_enrollment.partner_id` (FK to partner_accounts); civs created post-v1.80.0 with no partner_accounts row have unfillable FK — [warroom.py:44-130, 384-425](Haven-UI/backend/routes/warroom.py)
- **STALE** `tagColors.js` hardcoded list (7 civs) — every other civ falls through to hash palette / generic indigo, not `civilizations.region_color` — [tagColors.js:19-60](Haven-UI/src/utils/tagColors.js) + [DiscordTagBadge.jsx]
- **POLISH** PartnerManagement.jsx file still in tree (lazy-imported, never rendered) — dead chunk shipped in bundle — [PartnerManagement.jsx](Haven-UI/src/pages/PartnerManagement.jsx) + [App.jsx:27, 164](Haven-UI/src/App.jsx)
- **POLISH** `useDateFormat` hook exists but most pages still raw `new Date(x).toLocaleString()` — 147 raw occurrences across 51 files
- **POLISH** `star_color` vs `star_type` field aliasing — only one edit form handles both; all other reads use `star_type`. Backend should normalize on intake — [SystemApprovalTab.jsx:1022, 1113](Haven-UI/src/components/approvals/SystemApprovalTab.jsx) + many read sites
- **POLISH** Only Search.jsx URL-scopes by `?reality=&galaxy=` — system/region detail pages don't propagate reality through links; Permadeath player shares "/systems/123" and recipient sees Normal view
- **POLISH** CivilizationManagement detail vs UserManagement render `enabled_features_default` differently (joined string vs checkbox grid)
- **POLISH** ApiKeys.jsx copy still references "NMS Save Watcher companion app" — post-v1.69 that's just `haven_extractor` — [ApiKeys.jsx:121, 206, 234, 340, 439-441](Haven-UI/src/pages/ApiKeys.jsx)
- **POLISH** CommunityStats upload-method bar math `manualPct + extractorPct = 100` silently wrong when keeper rows exist — [CommunityStats.jsx:127-129](Haven-UI/src/pages/CommunityStats.jsx)
- **POLISH** AuthContext `user.defaultCivTag` (camelCase) vs Profile.jsx setter `default_civ_tag` (snake_case) — naming conflict; bug surface if buildUserFromData mapping ever breaks

---

## Suggested triage order

**Round 1 — BROKEN items (1-2 hours):**
- Top 10 list. Navbar pending badge, public Dashboard admin gate, Wizard personal_discord_username pollution, Personal-bucket Person-drill-down, keeper_bot timeline+breakdown, tier-5 edit gate, member login response, DiscoveryType "all" copy, URLBar From Map stub, DiscoverySubmitModal kill-or-mount.

**Round 2 — kill the "Partner" word (1 sweep):**
- Settings (3 sections), Profile/UserManagement TIER_LABELS, PARTNER_FEATURES const, AdminLoginModal tab, PartnerAnalytics page, PendingApprovals copy, SubAdminManagement copy. Replace "Partner" → "Civilization Leader" / "Civilization". Delete dead PartnerManagement.jsx.

**Round 3 — wire keeper_bot end-to-end:**
- Backend analytics CASE statements get a 3rd arm. Frontend gets a 3rd tab on Profile, 3rd bar segment on CommunityStats, friendly labels in PendingApprovals + ApprovalAudit. Source-aware color/label map.

**Round 4 — "Personal" bucket consolidation:**
- Backend write-side normalizer (lowercase on save). `isPersonalTag()` helper for frontend. Drop "Personal" from Profile default-community dropdown. Fix `/api/public/community-regions` + `/api/public/contributors` Personal-bucket SQL.

**Round 5 — DiscordTagBadge / tagColors migration:**
- Component reads from `getTagColorFromAPI()` first, hash-palette fallback only on miss. Always render `display_name` with `tag` as tooltip. Delete tagColors.js hardcoded list. Eager-prime cache on ThemeProvider mount.

**Round 6 — Wizard for-members polish:**
- Skip "Your Discord Username" field when session exists. Don't pop personal modal for logged-in. Initialize discord_tag from `user.defaultCivTag` synchronously so red border doesn't flash. Don't write personal_discord_username unless tag === personal.

**Round 7 — everything else** (CONFUSING + STALE that didn't make earlier rounds + POLISH grab-bag). Most are 1-line fixes.

---

## What this audit found vs the previous one

The previous (2026-05-13) audit was severity-based code review focused on security + data integrity. This one walked the user journeys looking for what feels wrong.

The overlap is small — different blast radius. This audit caught the "the civs migration is half-done in the UI" theme that's invisible from a code-review angle but blindingly obvious to a user clicking around. Most of these are 1-line fixes; the value is having them grouped so the patterns become repeatable refactors instead of one-off bug reports.
