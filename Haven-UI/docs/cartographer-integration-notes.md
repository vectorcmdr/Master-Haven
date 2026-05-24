# Cartographer v10 — API Integration Notes

Discovery deliverable for the v10 Cartographer → Map-tab integration (Step 2 of
`dispatch-cartographer-v10.md`). Maps every field the mockup consumes to a data
source, documents the snapshot wire format, and records the production map
features that still need porting.

**Source mockup:** `haven-cartographer-v10_2.html` (canonical — it has the locked
`zoomBoost` tuning the base `-v10.html` is missing).

---

## TL;DR

- **One new endpoint** is needed: `GET /api/map/snapshot`. It replaces the
  mockup's baked `<script id="snapshot">` blob.
- **Extended on-click detail needs no new endpoint** — the mockup already calls
  the existing `GET /api/systems/search?q=<glyph>&limit=1` then
  `GET /api/systems/{id}`.
- **Live-ping needs no change** — the mockup pings the existing `GET /api/stats`.
- The dispatch's Step 2 field table listed **9** fields. The mockup actually
  reads **19** top-level snapshot fields. Emitting only the 9 would break the
  detail card, glyph→live lookup, planet list, and every color/label lookup.

---

## The map tab today (Step 1 finding)

The "Map" tab is **not** a React route. `Navbar.jsx:113` is a plain
`href: '/map/latest'`. The backend serves it as static HTML:

| Route | Handler | Serves |
|---|---|---|
| `/map/latest` | `control_room_api.py:3401` | `dist/VH-Map-ThreeJS.html` (falls back to `public/`) |
| `/map/region` | `control_room_api.py:3450` | `VH-Map-Region.html` |
| `/map/system/{id}` | `control_room_api.py:3660` | `VH-System-View.html` (+ injected data) |
| `/map/static`, `/map/assets` | mounts (`:743`, `:746`) | map static assets |

The current galaxy map already loads its data **async** from
`GET /api/map/regions-aggregated` (`routes/systems.py:213`) — that endpoint is
the prior art and data-source model for `/api/map/snapshot`.

Integration approach (Parker's call): **static HTML.** The v10 file becomes a
new static map served at `/map/latest`; the only code change inside it is
swapping `JSON.parse(scriptTag.textContent)` for
`await fetch('/api/map/snapshot').then(r => r.json())`.

---

## Full snapshot field contract (19 fields)

Decoded in `parseSnapshot()` and consumed across the app. Index pools (`st`,
`ti`, `biomeIdx`, `sizeIdx`, `sentIdx`) are `Uint8`/`Uint16` arrays whose values
index into the parallel string pools (`star_types`, `tag_pool`, `biomes`,
`sizes`, `sentinel`). This is the mockup's own compression scheme — we reproduce
it on the server.

| Field | Wire type | In dispatch table? | Source | Notes |
|---|---|---|---|---|
| `n` | int | ✅ | `COUNT` of mapped systems | total system count |
| `pos` | b64 Float32 (3·n) | ✅ | `systems.x, y, z` | true NMS display coords (X/Z ±2048, Y ±128) — used as-is |
| `st` | b64 Uint8 (n) | ✅ | `systems.star_type` → pool index | |
| `ti` | b64 Uint8 (n) | ✅ | `systems.discord_tag` → `tag_pool` index | |
| `hp` | b64 Uint8 (n) | ✅ | `EXISTS planets WHERE system_id` | hasPlanets flag |
| `hs` | b64 Uint8 (n) | ✅ | `EXISTS space_stations WHERE system_id` | hasStation flag |
| `rpos` | b64 Float32 (3·rn) | ✅ | `AVG(x,y,z)` per region | region centroid display positions |
| `rcount` | b64 Uint16 (rn) | ✅ | `COUNT(*)` per region | systems per region |
| `regions` | array of obj | ✅ | aggregated regions | `{rx, ry, rz, name, count, tag}` |
| `names` | array[str] (n) | ❌ **missing** | `systems.name` | detail/hover card title |
| `glyphs` | array[str] (n) | ❌ **missing** | `systems.glyph_code` | key for the live `/api/systems/search` lookup |
| `star_types` | array[str] | ❌ **missing** | distinct star types | pool for `st`; drives shader palette + legend |
| `tag_pool` | array[str] | ❌ **missing** | distinct discord tags (`''` at 0 = untagged) | pool for `ti` |
| `tag_colors` | obj | ❌ **missing** | `GET /api/discord_tag_colors` `.colors` | `{tag: {color, name}}` — region/system tint |
| `biomes` | array[str] | ❌ **missing** | distinct planet biomes (`''` at 0) | pool for planet `biomeIdx` |
| `sizes` | array[str] | ❌ **missing** | distinct planet sizes (`''` at 0) | pool for planet `sizeIdx` |
| `sentinel` | array[str] | ❌ **missing** | distinct sentinel levels (`''` at 0) | pool for planet `sentIdx` (decoded; not yet rendered) |
| `planets_by_idx` | obj | ❌ **missing** | `planets` + `moons` | sparse `{systemIdx: [planetTuple, …]}` |
| `rn` | int | ❌ **missing** | region count | length of `rpos`/`rcount`/`regions` |

### Pool examples (from the baked snapshot, to reproduce exactly)

```
star_types = ['Yellow','Red','Green','Blue','Purple']
sizes      = ['', 'Small', 'Medium', 'Large']
biomes     = ['', 'Lush', 'Toxic', 'Radioactive', 'Frozen', 'Scorched', …]  (29)
tag_pool   = ['', 'AA', 'ACSD', 'AP', 'B.E.S', 'C&C', 'EVRN', 'GHUB', …]    (28)
tag_colors = { 'GHUB': {color:'#…', name:'GHUB'}, 'personal': {…}, … }       (from /api/discord_tag_colors)
```

### `planets_by_idx` tuple format

Sparse dict keyed by **stringified system index** (matches `pos`/`names` order),
value is an array of planet tuples:

```
[ name, biomeIdx, sizeIdx, sentIdx, flags, moonCount, planetIdx, isMoon ]
```

`flags` is a bitfield (mockup `showDetail` at `:2680`):

| Bit | Value | Planet column |
|---|---|---|
| RINGS | 1 | `has_rings` |
| GAS GIANT | 2 | `is_gas_giant` |
| WATER | 4 | `water_world` |
| BUBBLE | 8 | `is_bubble` |
| FLOATING | 16 | `is_floating_islands` |
| DISSONANT | 32 | `is_dissonant` |
| INFESTED | 64 | `is_infested` |
| EXTREME WX | 128 | `extreme_weather` |

`moonCount` = rows in `moons` for that planet. `isMoon` = `planets.is_moon`.

> **Mockup vs. real data:** the baked blob only populated `planets_by_idx` for
> 542 of 10,311 systems (a file-size shortcut for a static mockup). The real
> endpoint can populate it for every system that has planet rows (~7.5k locally),
> so the detail panel is filled straight from the snapshot instead of waiting on
> the live MORE-DETAILS fetch. This is the main size lever — see §Size/caching.

---

## Extended on-click detail (no new endpoint)

`expandDetail()` (mockup `:2741`) enriches the selected system on demand:

1. `GET /api/systems/search?q=<glyph_code>&limit=1` → first hit's `id`
2. `GET /api/systems/{id}` → full record

It reads these fields off `/api/systems/{id}` (all already returned by that
endpoint via `SELECT *`): `stellar_classification`, `economy_type`,
`economy_level`, `conflict_level`, `dominant_lifeform`, `fauna`, `flora`,
`sentinel`, `personal_discord_username` / `discovered_by`, `visit_date`,
`completeness_grade`, and `planets[]` with `weather`, `sentinel_level`, `fauna`,
`flora`, `common_resource`, `uncommon_resource`, `rare_resource`, `materials`,
`name`, `is_moon`. **No backend change required.**

Live-status pill: `pingLive()` (`:3027`) hits `GET /api/stats` (exists).

---

## Edge cases the endpoint handles

- **NULL `star_type`** (~42% of local rows): not representable in the 5-entry
  pool. Endpoint appends `'Unknown'` to `star_types` only when NULLs exist and
  maps them to that index; the ported HTML palette builder + legend get a
  neutral-grey fallback for `Unknown`. (Data correctness, not visual tuning —
  shaders/`zoomBoost`/`CROSSFADE`/fog/FOV untouched.)
- **Case-split tags** (`personal` vs `Personal`): kept as distinct `tag_pool`
  entries to match `tag_colors` keys exactly; not merged here (analytics owns
  consolidation).
- **NULL `region_x/y/z`** (6 local rows): excluded from region aggregation,
  still placed as systems via `pos`.
- **Biomes/sizes outside the mockup color maps** (264 distinct biomes vs ~28 in
  `BIOME_COLOR`): fall back to the mockup's default grey swatch — no error.

---

## Production map features to port (from the sibling static maps)

The v10 mockup is visually ahead but missing what the live `VH-Map-*.html` files
already implement, in the **same vanilla-JS idiom** (so these are copy-from-sibling,
not rewrites):

| Feature | Lives in today | Port target |
|---|---|---|
| `?focus=system:id\|region:rx,ry,rz\|civ:tag\|user:name` + pulse-ring + auto-pan | `VH-Map-ThreeJS.html` | new map file |
| Cross-layer breadcrumb (galaxy ↔ region ↔ system, focus carried) | all three | new map file (or keep 3-page split) |
| Civ/contributor territory filter (`focus_civ`/`focus_user` chip) | `VH-Map-ThreeJS.html` | new map file |
| Embed mode (`?embed=true&hideUI=true`, Dashboard iframe) | `VH-Map-ThreeJS.html` | new map file |
| Region & system drill-down pages | `VH-Map-Region.html`, `VH-System-View.html` | reuse as-is or fold into v10 tiers |
| SearchOverlay → map deep-links | `SearchOverlay.jsx` (React) | unchanged (still full-page `href`) |
| Civ color theming | `/api/discord_tag_colors` | already in snapshot via `tag_colors` |

These are **out of scope for the first integration pass** (get v10 rendering on
real data first); they're listed so the follow-up work is scoped.

---

## Size / caching (Step 3 concern)

Snapshot payload ≈ positions (12 B/system) + 4 flag/index arrays (1 B each) +
names + glyphs (12 B each) + `planets_by_idx`. For the local dataset this is on
the order of low-MB JSON pre-gzip; gzip cuts base64+JSON ~3–4×. The endpoint
should cache the built blob in-memory keyed on the newest `systems.modified_at`
(or row count) so it isn't rebuilt per request — matches the dispatch's v1
caching guidance. Build cost on the Pi is dominated by the `planets_by_idx`
join; cache makes the steady-state cost ~zero.
