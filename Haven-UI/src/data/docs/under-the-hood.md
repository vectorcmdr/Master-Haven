# Under the Hood

How Haven actually works — the data pipeline, the approval workflow, the math behind glyph decoding, and the reverse-engineered structure of the No Man's Sky galactic grid. This is the long doc. Settle in.

## The Architecture

Haven is a four-tier system that turns gameplay into a public map. Each tier hands off to the next:

1. **Capture** — a Voyager visits a system in No Man's Sky. The Haven Extractor mod (or the in-browser Wizard, or Keeper on Discord) records what they saw.
2. **Submit** — the captured data is POSTed to Haven's backend at [havenmap.online](https://havenmap.online/) and lands in the *pending* queue.
3. **Review** — an admin from the submitter's civilization opens the pending queue, checks the submission, and approves or edits it.
4. **Publish** — approved data moves into the live tables and shows up on the 3D map, in browse views, and in community stats.

The whole flow is designed so a Voyager can submit during a session and see the result on the live map within a day. No CMS, no marketing approval, no batched releases — submissions ship as fast as their reviewers move.

## The Mapping Pipeline

The three submission paths converge in the same backend, but they collect data differently.

### Path 1: The Wizard (manual web)

The Wizard is a step-by-step form. Voyagers pick glyphs from a visual picker, choose galaxy and reality, then fill in whatever they know about the system. Each field is optional; the *completeness grade* (covered below) reflects what's filled in. The Wizard is the slowest path but the most flexible — Voyagers can attach photos, write descriptions, and override anything.

### Path 2: The Haven Extractor (PC mod)

The Extractor is a Python mod loaded by [pyMHF](https://pypi.org/project/pyMHF/). It hooks several No Man's Sky functions — most importantly `cTkLanguageManagerBase.Translate`, the player-state struct reader, and `GenerateCreatureRoles` — and captures system data live as the Voyager warps and explores.

The Extractor's job is harder than it looks. NMS doesn't expose system data through any clean API; it lives scattered across memory in C++ structs whose offsets shift with every game update. The current Extractor uses a layered resolution strategy:

1. **Direct memory read.** Read fixed-offset values like `mUniverseAddress` (a packed 64-bit galactic coordinate), `RealityIndex`, `DifficultySettingPreset`, and the `SentinelsPerDifficulty` array.
2. **Hook capture.** Subscribe to `GenerateCreatureRoles` to grab per-planet info while the game's about to populate the planet's display strings.
3. **Translate cache.** Subscribe to `cTkLanguageManagerBase.Translate` and build an in-memory map of `text_id → display_text` so we can resolve adjectives like *Bountiful* / *Copious* / *Empty* the same way the game does.
4. **PAK/MBIN cache.** As a backup, parse the game's language MBIN files directly. This lets the Extractor resolve adjectives even before the in-game Translate hook has fired for that text ID.

When Voyagers click **Export**, the Extractor batches every system they captured during the session and POSTs them to `/api/extraction` with a per-user API key.

### Path 3: Keeper (Discord)

For console players who can't run a PC mod, Keeper is a Discord bot built by Stars (community member). It accepts screenshot-based submissions via slash commands in your civilization's `#discoveries` channel and posts them to Haven through its own authenticated API key. From Haven's perspective, Keeper submissions and Extractor submissions look nearly identical — both authenticate, both land in the same pending queue, and both are tagged with their `source` so analytics can split them apart later.

## The Approval Workflow

Every submission lands in `pending_systems` (or `pending_discoveries`, `pending_region_names`) before it shows on the live map. The approval queue is scoped per civilization — a partner admin only sees their own community's pending items, never another civilization's.

When an admin approves a submission, several things happen in order:

1. **Self-approval check.** Haven refuses to let an admin approve their own submission. The check uses `profile_id` if present, falls back to a normalized username comparison. This is a hard rule, not a setting.
2. **Edit-vs-new detection.** If the submission's glyph code matches an existing system in the same galaxy and reality (last 11 characters of the glyph match — the planet index can differ), Haven treats the submission as an *edit* of the existing system rather than a new entry. The matching logic lives in `find_matching_system()` and is shared by every approval path, including batch approvals and direct extractor inserts.
3. **Audit log.** Every approval, rejection, edit, or batch action writes a row to `approval_audit_log` with the actor's identity, the action, and a snapshot of what changed. This is queryable from `/admin/audit`.
4. **Activity log.** A short human-readable line goes into `activity_logs` so the live activity feed shows what just happened.
5. **Completeness recalculation.** The system's completeness grade is recomputed and cached on the row.

The whole sequence runs in a single SQLite transaction. If anything fails, nothing moves.

## Completeness Grading

Every system gets a letter grade — **C / B / A / S** — based on how much data it has. The grade is a single integer percentage (0–100) translated into a letter at render time. The score is weighted across seven categories:

| Category | Weight | What it measures |
|---|---|---|
| **System core** | 15 | Galaxy, reality, glyph, name, star color |
| **System extras** | 10 | Star spectral class, system economy, conflict level, dominant lifeform |
| **Planet coverage** | 20 | All N planets / moons present (the game tells us how many to expect) |
| **Planet environment** | 15 | Per-planet biome, weather, sentinel level |
| **Planet life** | 15 | Per-planet flora and fauna adjectives. Biome-aware: *Dead* / *Airless* / *Gas Giant* don't lose points for missing flora/fauna |
| **Planet detail** | 15 | Per-planet resources, special features, photos |
| **Space station** | 10 | Station present (or system marked *Abandoned*, in which case full credit) |

Edge cases the scoring handles:

- **Abandoned systems.** Some systems genuinely have no station, no economy, and no conflict. Setting *economy = Abandoned* gives full credit for the missing fields rather than docking points.
- **Dead/Airless planets.** Biome-aware life scoring means a Dead planet's missing fauna is treated as *correct* (there is no life), not *missing*.
- **Bubble / Floating Islands / Gas Giant** and other special features add to the *Planet detail* bucket.

The full implementation is in `Haven-UI/backend/services/completeness.py`. The grade is recalculated on every save, approval, or edit.

## The Glyph & Portal Coordinate System

This is where it gets interesting. Glyphs aren't decoration — they're a packed coordinate system that lets Haven place every submitted system on the right galactic grid square. The community-built understanding of the glyph system is documented below by **WhrStrsG** (whrstrsg@gmail.com), reproduced with permission.

> **Welcome, Voyager! Ours is a journey of numbers. Come and learn the stars!**
>
> Portal glyphs encode galactic coordinates in a predictable structure. Once you know the structure, you can intentionally aim portals to travel through the galaxy.

### The Basics

The No Man's Sky galaxies are split into **Regions, Systems, and Planets**.

- Regions can only be viewed from the galactic map by hitting **Expand** while on a system.
- Systems can be traveled to from the map or viewed through the discoveries page.
- Planets can be accessed in each system, or portaled to.

The glyphs are a hexadecimal sequence: a 16-digit system of letters and numbers.

![Glyph hexadecimal sequence](/haven-ui/docs/images/glyph-hex-sequence.jpg)

It is important to remember the sequence starts at `(00)` / `(000)` and ends at `(FF)` / `(FFF)`.

The sequence does **not** cycle to `(10)` / `(010)` after `(09)` / `(009)` — it continues to the next glyph, `(A)`:

> Example: `(008) → (009) → (00A) → (00B)`

The sequence only cycles after the last glyph, `(F)`:

> Example: `(00E) → (00F) → (010) → (011)`

### The Galactic Address

The Galactic address is split into small groups of digits. These groups signify the planet, system, and region you are traveling to. Think of a portal address as:

```
(p) (ssi) (yy.zzz.xxx)
```

Each section controls a different aspect of where you arrive.

#### 1. `(p)` — Planet Index (Glyph 1)

Determines the planet within the target system. If you only care about reaching the system, this value barely matters. As there can only ever be between 2 and 6 celestial bodies per system, this value will only ever use the glyphs: `1, 2, 3, 4, 5, 6`.

#### 2. `(ssi)` — Star System Index (Glyphs 2–4)

These glyphs define the local system within a larger region. Each region contains between 200 and 600 systems.

| System type | Range |
|---|---|
| **Yellow systems** | `(001)` to `(122)` |
| **Coloured systems** | starts at `(123)`, values stay below `(250)` |
| **Purple systems** | `(3E9)` to `(429)` |

If you're targeting a known system type — such as a region's *Glass star* or a specific star colour — this range matters. Otherwise, treat these glyphs as rough positioning.

![Solar system index visualization](/haven-ui/docs/images/solar-system-index.jpg)

#### 3. `(yy.zzz.xxx)` — Region Coordinates (Glyphs 5–12)

These are the most important glyphs. They determine your position in the galaxy and can place you within ~500 LY of any destination.

| Axis | Glyphs | Meaning |
|---|---|---|
| `(yy)` | 2 | Galactic height (core ↔ rim) |
| `(zzz)` | 3 | Galactic North ↔ South |
| `(xxx)` | 3 | Galactic East ↔ West |

Hard rules:

- `(Y)` will never be `80`
- `(Z)` will never be `(800)`
- `(X)` will never be `(800)`

> **If you see these values, the address will be invalid.**

### The Galactic Grid

Each galaxy is `(y)256 × (z)4096 × (x)4096` regions in size — about **4.2 billion** total regions. The center of each galaxy is always `(00.000.000)`.

- As you go **"Up"** (`yy`) along the axis the glyphs increase from `(00)` to `(7F)`. At the top, the sequence ends, then continues from `(81)` to `(FF)`.
- As you go **"East"** (`xxx`) or **"South"** (`zzz`) along the axis the glyphs increase from `(000)` to `(7FF)`. At the outer edges, the sequence ends, then continues from the **"Western"** or **"Northern"** edge to the center from `(801)` to `(FFF)` along the axis. This makes all outermost corner regions some combination of `(801)` and `(7FF)`.

> Examples: NE corner = `(801.7FF)` or SE corner = `(7FF.7FF)`

![Galactic grid orientation](/haven-ui/docs/images/galactic-grid-1.jpg)

![Galactic grid wraparound](/haven-ui/docs/images/galactic-grid-2.jpg)

### The Center

Around the core of each galaxy, there is a void. Although this void still contains glyphs, they are inaccessible through normal means.

As the void is spheroid, the `(z)` and `(x)` parameters change as height increases / decreases. The core void accounts for a ~5-region sphere around the core.

- Regions `(z)` and `(x)` coords around `(yy) = (00)` should never be less than `(005)` or above `(FFA)`.
- Regions `(z)` and `(x)` coords around `(yy) = (05)` can be anything but `(800)`.

This means **the last 8 glyphs do almost all the work**. Adjusting `(yy.zzz.xxx)` lets you jump between regions or across the entire map, map entire regions, aim near specific places, and reconstruct known locations from coordinates. The first 4 glyphs mostly refine which system you land in once you're already close.

### The Solar System Index

There are a few set solar system index `(ssi)` coordinates worth knowing about: two **Shadow stars** per region, one **Glass star**, **black holes**, and **The Atlas interface**.

- **Black holes** always generate at `(079)` on the `(ssi)` in a region.
- **The Atlas interface** always generates at `(07A)` on the index.
- **The first Shadow star** is the highest `(ssi)` in a given region. It can only be reached through the galaxy map, but it can be found by portaling to the corresponding region "Glass star," which is always `(3E8)` on the solar system index. This Glass star cannot be reached from the galactic map and will not display from the map. Instead, the map will display that region's Shadow star. You can reach it by traveling to another system and back, via the galactic map.
- **The second Shadow star** is the highest possible `(ssi)` for purple systems in any region: `(429)`. It cannot be portaled to. Intentional travel to this system is difficult. *Research ongoing.*
- **Phantom stars.** There exist within each region 4095 systems; the game only generates between 200 and 600 accessible systems for players to travel to. The rest are *phantom stars*. These systems still contain glyph coordinates but cannot be portaled to through normal means.
- **Glitched / phantom regions.** Around the core of each galaxy is a void. There are still regions of stars in this void; they don't show and are inaccessible to most explorers. These are phantom regions, with very few explorers dedicated to discovering and mapping them.

### History

Before glyphs, galactic coordinates were determined and mapped with signal boosters. A different hexadecimal system displayed as: `(ABCD:1234:5678:90AB)`.

Early explorers used these coordinates to decode the galactic grid and begin charting the galaxy even before HG's Galactic Atlas. Early explorers and communities such as **Pahefu** and **Galactic Hub** developed tools like the [Pilgrim Star Path](https://pahefu.github.io/pilgrimstarpath/) to help explorers with wider galactic travel.

After the addition of the Glyph portal system, communities immediately began extensive research, such as ETARC's *Solar System Index Research* — an early deep dive into the stars/systems index and an investigation of what are now called Phantom systems: [Solar System Index spreadsheet](https://docs.google.com/spreadsheets/d/1pI91h0M9633f9nFk4yCb230GtYRRazQaFHEZfwuxNLs/edit?usp=drivesdk).

Since the beginning, explorers of the No Man's Sky community have been invested and active in deep exploration and research. Many tools and exchanges have been developed over time to aid Travelers in their exploration and research.

#### Glyph repositories and community exchanges

- [ETARC's early coordinate exchange thread](https://forums.atlas-65.com/t/galactic-coordinates-thread/2843/228?page=11)
- [NMSCE coordinate exchange (Reddit)](https://www.reddit.com/r/NMSCoordinateExchange/s/uusp9PA9Em)
- [NMSCE website](https://nmsce.com/)
- [Fandom: Civilized Space Euclid](https://nomanssky.fandom.com/wiki/Map:Civilized_Space_Euclid_Map)

#### Decoders / repository tools

- [The Portal Repository](https://portalrepository.com/glyph-decoder/#google_vignette)
- [RogerHN's NMS portal decoder](https://nmsportals.github.io/)

#### Mapping / discovery systems

- [The AGT's NAVI](https://mhebrard.github.io/nms-browser/)
- [Voyager's Haven map](https://havenmap.online/)
- [Had.sh](https://glyphs.had.sh/galaxy/1)
- [Pahefu's Hub management system for GHub](https://pahefu.github.io/nmsthehub/)

### References & Credits

- *Reference image 2* — Raven B+ team
- *Reference images 3 & 4* — [Gravnaut](https://www.reddit.com/r/NoMansSkyTheGame/s/bDYy7MvNef)
- *Reference image (system index)* — [Had.sh](https://glyphs.had.sh/galaxy/1)

**Author:** WhrStrsG &middot; whrstrsg@gmail.com

---

## Region Naming

Glyph coordinates give us a region, but the *name* of that region (e.g. *Wendrunda Cluster*, *Heumawalt Expanse*) is procedurally generated by the game. Haven captures both:

- **Procedural names** are computed by the vendored `nms_namegen` library (MIT, by Stuart). It mirrors the game's name-generation algorithm and runs entirely on the client. Every system the Extractor uploads carries a procedural name even if the Voyager hasn't yet seen it in-game.
- **Custom names** can be proposed by Voyagers through the Wizard. If a region doesn't have a name yet, anyone can propose one. The name lands in `pending_region_names` and goes through the same approval workflow as system submissions. Once approved, that custom name becomes the canonical display name for the region — but only within that **galaxy and reality**. The same region in Permadeath might end up with a different name proposed by a different Voyager, and that's fine.

The uniqueness key on the `regions` table is `(reality, galaxy, region_x, region_y, region_z)` — five columns, not three. Migration v1.49.0 made this change so the same coordinate triple in different galaxies can carry different names without conflict.

## How Submissions Are Sourced

Every approved row in `systems`, `discoveries`, and `regions` carries a `source` column with one of three values:

| Source | Meaning |
|---|---|
| `manual` | Submitted through the Wizard, no API key on the request. |
| `haven_extractor` | Submitted by an authenticated Extractor key — either a per-user `Extractor - <username>` key, the legacy shared `Haven Extractor` key, or the prototype `Haven` admin key. |
| `keeper_bot` | Submitted by Keeper using its dedicated `Keeper 2.0` API key. |

The canonical resolution lives in `resolve_source()` (`Haven-UI/backend/constants.py`) and runs on every submission path. Analytics dashboards and the public Source Breakdown chart split by this field, so `keeper_bot` traffic is correctly attributed to Keeper rather than the Extractor it shares an ingest endpoint with.

## The Live Map

The 3D galactic map at `/map/latest` is rendered with React Three Fiber and pulls a streamlined feed from `/api/galaxies/summary` and `/api/systems`. The map intentionally skips per-planet detail — that's reserved for the system detail page — and shows just enough to let Voyagers spot regions, navigate clusters, and pick a system to drill into.

Galactic coordinates from the glyph decoder are converted into 3D scene coordinates using the wraparound rules described in the WhrStrsG section above:

- `(yy) ≥ 0x80` → south of equator (the byte represents a *signed* 8-bit value)
- `(zzz)` and `(xxx) ≥ 0x800` → west / north of meridian (signed 12-bit)

The conversion matches what the game itself does internally and is what makes Haven's map align correctly with in-game galactic-map reference points.

## What's Cached, What Isn't

For performance on a Raspberry Pi 5, several values are precomputed and cached:

- **Completeness scores** are cached on `systems.is_complete` (legacy column name, now an integer 0–100). Recalculated on save / approve / edit.
- **Region populated counts** in `/api/db_stats` are recomputed on each request but distinct on `(reality, galaxy, rx, ry, rz)` to match the regions UNIQUE constraint introduced in v1.49.0.
- **Static photos** served via `CachedStaticFiles` set `Cache-Control: public, max-age=2592000, immutable` — 30 days. Filenames are immutable on upload (the WebP pipeline writes a fresh filename per upload and never overwrites), so long browser caching is safe.
- **WAL checkpointing** runs as a background asyncio task every 30 minutes to bound SQLite WAL growth on the Pi.

Everything else is read live from the database. There's no Redis, no in-memory query cache, no edge cache layer beyond Cloudflare for static assets.

---

> **Open question for the doc author:** add a section on the Travelers Exchange integration once Keeper v2 ships (the contribution → coin pipeline). It's not live yet, so this doc treats it as out of scope for now.
