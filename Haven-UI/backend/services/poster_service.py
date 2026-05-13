"""
Poster service — registry, render queue, Playwright lifecycle, cache I/O.

Single source of truth for every dynamically-rendered visual artifact in Haven
(Voyager Cards, Galaxy Atlases, Open Graph cards). Adding a new poster type =
one row in REGISTRY + one React component in src/posters/. Nothing else.

Design invariants (poster-system-plan.md):
  1. Adding a new poster type must be: registry entry + React component.
  2. Every poster component must set window.__POSTER_READY = true.
  3. The PNG endpoint is the single share-source for all consumers.
  4. Cache invalidation is event-driven first, TTL second.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from db import get_db_connection, get_db_path

logger = logging.getLogger('control.room')

# ============================================================================
# Configuration
# ============================================================================

# How long the headless browser will wait for window.__POSTER_READY
POSTER_READY_TIMEOUT_MS = 12000

# Hard ceiling on a single render (page load + screenshot)
RENDER_TIMEOUT_S = 18

# Concurrent render budget — protects Pi from being overwhelmed.
# Parker 2026-05-13: bumped 2→4 to let the startup pre-warm finish faster
# on the Pi 5. Empirically the bottleneck is single-page render latency
# (~1-2 s); four concurrent contexts stays well under the Chromium memory
# budget on the 8 GB Pi and roughly halves the warm-up wall time.
RENDER_CONCURRENCY = 4

# How long to wait before dropping cache rows that haven't been read
CACHE_PRUNE_AFTER_DAYS = 90

# Where rendered PNGs live on disk
def get_posters_dir() -> Path:
    """Resolve the poster cache directory under Haven-UI/data/posters/."""
    db_path = get_db_path()
    posters_dir = db_path.parent / 'posters'
    posters_dir.mkdir(parents=True, exist_ok=True)
    return posters_dir


# Where Playwright opens the SPA. In production this is the same backend that
# serves /api/posters/, so 127.0.0.1 + the port we're listening on works.
def get_render_base_url() -> str:
    return os.getenv('POSTER_RENDER_BASE', 'http://127.0.0.1:8005')


# ============================================================================
# Registry
# ============================================================================

@dataclass
class PosterTemplate:
    """Defines one renderable poster type.

    Adding a new poster type = add a row here + create the React component
    referenced by spa_route. The React component must self-fetch its data and
    set window.__POSTER_READY = true after first paint.
    """
    type: str                                # 'voyager', 'atlas', 'og_site', etc.
    version: int                             # Bump to invalidate all caches for this type
    width: int                               # Viewport width Playwright opens at
    height: int                              # Viewport height
    spa_route: str                           # SPA path Playwright loads, with {key} placeholder
    ttl_hours: int                           # Cache lifetime before automatic re-render
    public: bool = True                      # Whether the PNG endpoint is publicly fetchable
    requires_opt_in_check: bool = False      # If True, check user_profiles.poster_public for the key
    description: str = ''                    # Human-readable description for admin UI


REGISTRY: dict[str, PosterTemplate] = {
    'voyager': PosterTemplate(
        type='voyager',
        version=1,
        width=680,
        height=1040,
        spa_route='/poster/voyager/{key}',
        ttl_hours=24,
        requires_opt_in_check=True,
        description='Personal Voyager Card — 680x1040 stat-rich poster',
    ),
    'voyager_og': PosterTemplate(
        type='voyager_og',
        version=1,
        width=1200,
        height=630,
        spa_route='/poster/voyager_og/{key}',
        ttl_hours=24,
        requires_opt_in_check=True,
        description='Voyager Card OG variant — 1200x630 condensed for Discord/Twitter embeds',
    ),
    'atlas': PosterTemplate(
        type='atlas',
        version=1,
        width=680,
        height=920,
        spa_route='/poster/atlas/{key}',
        ttl_hours=24,
        description='Galaxy Atlas — 680x920 political map of one galaxy',
    ),
    'atlas_thumb': PosterTemplate(
        type='atlas_thumb',
        version=1,
        width=400,
        height=400,
        spa_route='/poster/atlas_thumb/{key}',
        ttl_hours=24,
        description='Galaxy Atlas thumbnail — 400x400 for Systems-tab cards',
    ),
    'og_site': PosterTemplate(
        type='og_site',
        version=1,
        width=1200,
        height=630,
        spa_route='/poster/og_site/global',
        # 1-hour belt-and-suspenders TTL. Event-driven invalidation (system
        # approval, region naming) is the primary path; this catches CSV
        # imports, direct DB edits, and other backdoor changes the hooks miss.
        ttl_hours=1,
        description='Global Haven OG card — replaces static haven-preview.png',
    ),
    'landing_og': PosterTemplate(
        type='landing_og',
        version=1,
        width=1200,
        height=630,
        spa_route='/poster/landing_og/global',
        # See og_site comment — same 1-hour safety-net TTL.
        ttl_hours=1,
        description='Landing-page OG card — cosmic-compass + wordmark + 3 live stats, served for havenmap.online/ embeds',
    ),
    'og_system': PosterTemplate(
        type='og_system',
        version=1,
        width=1200,
        height=630,
        spa_route='/poster/og_system/{key}',
        ttl_hours=24,
        description='Per-system OG card for /systems/:id share embeds',
    ),
    'og_community': PosterTemplate(
        type='og_community',
        version=2,
        width=1200,
        height=630,
        spa_route='/poster/og_community/{key}',
        ttl_hours=24,
        description='Per-community OG card for /community-stats/:tag share embeds',
    ),
    'region_thumb': PosterTemplate(
        type='region_thumb',
        # v3 (Parker 2026-05-11): cube bumped 200→280 px (was leaving a
        # third of the canvas empty), dot radius 1.5→2, recenter cx 130→165.
        # v2: star-color dots (was: community-tag dots); community color
        # moved to outer frame.
        version=3,
        width=600,
        height=300,
        # Region thumbs are keyed by `rx_ry_rz` and pass `galaxy`+`reality`
        # via the query string — see RegionThumb.jsx. The SPA route ignores
        # the query string but Playwright passes the full URL we build, so
        # the component still receives them through useSearchParams.
        spa_route='/poster/region_thumb/{key}',
        ttl_hours=24,
        description='Region thumbnail — 600x300 isometric voxel view of all systems in a region',
    ),
    'system_thumb': PosterTemplate(
        type='system_thumb',
        # v4 (Parker 2026-05-11 round 3): the v3 font bump never actually
        # reached this poster — SystemThumb had its own local Stat() func
        # that v2/v3 edits to the shared StatTile never touched. Replaced
        # the local with the shared component so the 19/24/16 fonts
        # finally land on the L4 cards.
        version=4,
        width=720,
        height=480,
        # Keyed by system_id. Pulls /api/systems/{id} and renders an orbital
        # diagram + stat tiles + glyph row.
        spa_route='/poster/system_thumb/{key}',
        ttl_hours=24,
        description='System thumbnail — 600x400 landscape with orbital diagram and stats',
    ),
}


def get_template(poster_type: str) -> Optional[PosterTemplate]:
    """Return the registered template, or None if unknown."""
    return REGISTRY.get(poster_type)


def list_templates() -> list[dict]:
    """Return registry as a list of dicts for the admin queue UI."""
    return [
        {
            'type': t.type,
            'version': t.version,
            'width': t.width,
            'height': t.height,
            'ttl_hours': t.ttl_hours,
            'requires_opt_in_check': t.requires_opt_in_check,
            'description': t.description,
        }
        for t in REGISTRY.values()
    ]


# ============================================================================
# Playwright lifecycle
# Keep one persistent browser process alive for the lifetime of the app.
# Booting Chromium per-request would burn ~3 seconds and 200MB of churn.
# ============================================================================

_browser = None  # Resolved lazily; set in lifespan startup
_browser_lock = asyncio.Lock()
_render_semaphore = asyncio.Semaphore(RENDER_CONCURRENCY)


async def init_browser():
    """Boot the persistent Playwright Chromium instance. Called from FastAPI lifespan."""
    global _browser
    async with _browser_lock:
        if _browser is not None:
            return _browser
        try:
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            _browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage'],  # Pi-friendly
            )
            # Stash the playwright handle on the browser so shutdown can stop it
            _browser._playwright_handle = playwright
            logger.info('Poster service: Playwright Chromium booted')
        except Exception as e:
            logger.exception(f'Poster service: failed to boot Playwright: {e}')
            _browser = None
            raise
    return _browser


async def shutdown_browser():
    """Tear down Playwright. Called from FastAPI lifespan shutdown."""
    global _browser
    if _browser is None:
        return
    try:
        playwright = getattr(_browser, '_playwright_handle', None)
        await _browser.close()
        if playwright is not None:
            await playwright.stop()
        logger.info('Poster service: Playwright shut down cleanly')
    except Exception as e:
        logger.warning(f'Poster service: shutdown error (non-fatal): {e}')
    finally:
        _browser = None


def is_browser_ready() -> bool:
    """Return True if the persistent browser is booted and reachable."""
    return _browser is not None


# ============================================================================
# Cache table I/O
# Schema (from migration v1.70.0):
#   poster_cache(id, poster_type, cache_key, template_version,
#                generated_at, data_hash, file_path, render_ms)
# ============================================================================

def _cache_lookup(poster_type: str, cache_key: str) -> Optional[dict]:
    """Return the cache row for (type, key) or None."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, poster_type, cache_key, template_version,
                   generated_at, data_hash, file_path, render_ms
            FROM poster_cache
            WHERE poster_type = ? AND cache_key = ?
            LIMIT 1
        ''', (poster_type, cache_key))
        row = cursor.fetchone()
        return dict(row) if row else None


def _cache_write(poster_type: str, cache_key: str, template_version: int,
                 data_hash: str, file_path: str, render_ms: int) -> None:
    """UPSERT a cache row.

    For region_thumb we additionally snapshot the current system_count so the
    threshold-based invalidation in routes/approvals.py knows when to drop.
    """
    system_count_at_render = None
    if poster_type == 'region_thumb':
        # cache_key is `rx_ry_rz`; count systems in that region
        try:
            parts = cache_key.split('_')
            if len(parts) == 3:
                rx, ry, rz = int(parts[0]), int(parts[1]), int(parts[2])
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute(
                        'SELECT COUNT(*) FROM systems WHERE region_x = ? AND region_y = ? AND region_z = ?',
                        (rx, ry, rz),
                    )
                    system_count_at_render = c.fetchone()[0]
        except Exception as e:
            logger.warning(f"Could not snapshot system_count for region_thumb {cache_key}: {e}")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO poster_cache
                (poster_type, cache_key, template_version, generated_at, data_hash, file_path, render_ms, system_count_at_render)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(poster_type, cache_key) DO UPDATE SET
                template_version = excluded.template_version,
                generated_at = excluded.generated_at,
                data_hash = excluded.data_hash,
                file_path = excluded.file_path,
                render_ms = excluded.render_ms,
                system_count_at_render = excluded.system_count_at_render
        ''', (
            poster_type, cache_key, template_version,
            datetime.now(timezone.utc).isoformat(),
            data_hash, file_path, render_ms, system_count_at_render,
        ))
        conn.commit()


def _cache_delete(poster_type: str, cache_key: str) -> Optional[str]:
    """DELETE a cache row, return the file_path that was removed (or None)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT file_path FROM poster_cache WHERE poster_type = ? AND cache_key = ?',
            (poster_type, cache_key),
        )
        row = cursor.fetchone()
        file_path = row['file_path'] if row else None
        cursor.execute(
            'DELETE FROM poster_cache WHERE poster_type = ? AND cache_key = ?',
            (poster_type, cache_key),
        )
        conn.commit()
        return file_path


# ============================================================================
# Disk size cap — protect the Pi from unbounded poster cache growth.
#
# Parker (2026-05-11): 4 GB ceiling, hysteresis to 3.5 GB after eviction to
# avoid thrash. Eviction order is generated_at-ascending (oldest first),
# which approximates LRU well — every cache write touches generated_at, so
# recently-rendered posters survive. Per-row file delete + DB row delete.
# ============================================================================

POSTER_CACHE_CEILING_BYTES = 4 * 1024 * 1024 * 1024   # 4 GB hard cap
POSTER_CACHE_FLOOR_BYTES = int(3.5 * 1024 * 1024 * 1024)  # evict down to 3.5 GB
EVICTION_CHECK_INTERVAL_S = 1800  # 30 minutes


def get_cache_disk_usage() -> int:
    """Sum bytes of every PNG under Haven-UI/data/posters/. Cheap walk."""
    total = 0
    posters_dir = get_posters_dir()
    for p in posters_dir.rglob('*.png'):
        try:
            total += p.stat().st_size
        except (FileNotFoundError, PermissionError):
            pass
    return total


def evict_oldest_until_under(target_bytes: int) -> dict:
    """Delete oldest cache entries until cache disk usage drops below target.

    Skips og_site / landing_og (global, cheap to keep) and atlas (the per-
    galaxy posters get hit often enough). Returns a small report dict.
    """
    keep_types = {'og_site', 'landing_og'}
    initial = get_cache_disk_usage()
    if initial <= target_bytes:
        return {'evicted': 0, 'initial_bytes': initial, 'final_bytes': initial}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT poster_type, cache_key, file_path
            FROM poster_cache
            ORDER BY generated_at ASC
        ''')
        rows = cursor.fetchall()

    evicted = 0
    current = initial
    for row in rows:
        if current <= target_bytes:
            break
        if row['poster_type'] in keep_types:
            continue
        try:
            file_path = row['file_path']
            if file_path:
                p = Path(file_path)
                if p.exists():
                    size = p.stat().st_size
                    p.unlink()
                    current -= size
            with get_db_connection() as conn2:
                conn2.cursor().execute(
                    'DELETE FROM poster_cache WHERE poster_type = ? AND cache_key = ?',
                    (row['poster_type'], row['cache_key']),
                )
                conn2.commit()
            evicted += 1
        except Exception as e:
            logger.warning(f"Eviction failed for {row['poster_type']}/{row['cache_key']}: {e}")

    final = get_cache_disk_usage()
    logger.info(f"Poster eviction: dropped {evicted} entries, {initial} → {final} bytes")
    return {'evicted': evicted, 'initial_bytes': initial, 'final_bytes': final}


async def periodic_eviction_task(interval_seconds: int = EVICTION_CHECK_INTERVAL_S):
    """Background loop. Schedule via the app's startup lifespan."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            current = get_cache_disk_usage()
            if current > POSTER_CACHE_CEILING_BYTES:
                logger.info(f"Poster cache at {current} bytes (> {POSTER_CACHE_CEILING_BYTES}); evicting…")
                evict_oldest_until_under(POSTER_CACHE_FLOOR_BYTES)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Eviction task tick failed (continuing): {e}")


def invalidate(poster_type: str, cache_key: str) -> bool:
    """Drop the cache entry for (type, key) and remove the PNG from disk.

    Called by approval handlers when underlying data changes (system approved,
    region named, etc.). Next consumer request will re-render fresh.

    Returns True if a row was dropped, False if no entry existed.
    """
    file_path = _cache_delete(poster_type, cache_key)
    if file_path:
        try:
            p = Path(file_path)
            if p.exists():
                p.unlink()
        except Exception as e:
            logger.warning(f'Poster invalidate: failed to remove {file_path}: {e}')
        logger.info(f'Poster invalidate: dropped {poster_type}/{cache_key}')
        return True
    return False


def is_cache_fresh(poster_type: str, cache_key: str, row: dict) -> bool:
    """Decide whether a cache row can be served as-is.

    Fresh if:
      - template_version matches current registry version (auto-invalidates on bump)
      - file exists on disk
      - generated_at is within the template's TTL
    """
    template = REGISTRY.get(poster_type)
    if template is None:
        return False
    if row.get('template_version') != template.version:
        return False
    file_path = row.get('file_path')
    if not file_path or not Path(file_path).exists():
        return False
    try:
        generated_at = datetime.fromisoformat(row['generated_at'].replace('Z', '+00:00'))
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - generated_at
        if age > timedelta(hours=template.ttl_hours):
            return False
    except (ValueError, KeyError, TypeError):
        return False
    return True


# ============================================================================
# Render
# ============================================================================

def _build_render_url(template: PosterTemplate, cache_key: str) -> str:
    """Construct the SPA URL Playwright opens for this template/key."""
    base = get_render_base_url().rstrip('/')
    # Mount under /haven-ui because that's the SPA base path in production
    # (vite.config.mjs base: '/haven-ui/'). Renderer URL is the chrome-less
    # /poster/:type/:key route.
    spa_path = template.spa_route.format(key=cache_key)
    return f'{base}/haven-ui{spa_path}'


def _build_output_path(template: PosterTemplate, cache_key: str) -> Path:
    """Where this poster's PNG lives on disk."""
    safe_key = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in cache_key)[:64]
    return get_posters_dir() / template.type / f'{safe_key}_v{template.version}.png'


async def _render(template: PosterTemplate, cache_key: str, output_path: Path) -> int:
    """Open the SPA route in headless browser, wait for ready flag, screenshot.

    Returns render duration in milliseconds. Raises on timeout or error.
    """
    if not is_browser_ready():
        await init_browser()

    url = _build_render_url(template, cache_key)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f'Rendering {template.type}/{cache_key} from {url}')

    async with _render_semaphore:
        # `start` lives INSIDE the semaphore so render_ms reflects only the
        # actual Chromium work, not the time spent waiting in the queue.
        # Parker (2026-05-13): before this fix, pre-warm dispatching 300
        # tasks via asyncio.gather inflated render_ms to 60-90s — the
        # actual render was sub-2s; the rest was queue wait. Logging the
        # wait time too gives us a real diagnostic if the queue is hot.
        wait_start = time.monotonic()  # set after we own the slot
        start = wait_start
        context = await _browser.new_context(
            viewport={'width': template.width, 'height': template.height},
            device_scale_factor=2,  # Render at 2x for crisp images
        )
        try:
            page = await context.new_page()
            try:
                # Navigate and wait for the poster's ready flag
                await page.goto(url, wait_until='domcontentloaded', timeout=RENDER_TIMEOUT_S * 1000)
                # Wait for the JS flag the React component sets after data + render
                await page.wait_for_function(
                    'window.__POSTER_READY === true',
                    timeout=POSTER_READY_TIMEOUT_MS,
                )
                # Brief settle so any final layout shifts (font swap, etc.) commit
                await page.wait_for_timeout(150)
                await page.screenshot(
                    path=str(output_path),
                    full_page=False,
                    omit_background=False,
                    type='png',
                    clip={'x': 0, 'y': 0, 'width': template.width, 'height': template.height},
                )
            finally:
                await page.close()
        finally:
            await context.close()

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(f'Rendered {template.type}/{cache_key} in {duration_ms}ms')
    return duration_ms


# ============================================================================
# Data hash (skip-render optimization)
# ============================================================================

def compute_data_hash(poster_type: str, cache_key: str) -> Optional[str]:
    """Hash of the underlying data so we can skip re-renders that wouldn't differ.

    Returns None if no cheap hash source is known for this poster type — in
    that case we always re-render when TTL elapses. Intended to be extended as
    we add cheap data signatures (e.g., max(submission_date) for voyager).
    """
    # Future optimization: compute hashes per poster type from inexpensive
    # SQL queries. For now we rely on TTL + event-driven invalidation.
    return None


# ============================================================================
# Public entry point
# ============================================================================

async def get_or_render(poster_type: str, cache_key: str) -> Optional[Path]:
    """Return the file path to a cached or freshly-rendered poster PNG.

    Returns None if the poster type is unknown.

    Cache lookup → return file path if fresh.
    Else render → write cache → return file path.

    Caller (the route) handles 404, opt-in checks, headers.
    """
    template = REGISTRY.get(poster_type)
    if template is None:
        return None

    # Check cache first
    row = _cache_lookup(poster_type, cache_key)
    if row and is_cache_fresh(poster_type, cache_key, row):
        return Path(row['file_path'])

    # Render fresh
    output_path = _build_output_path(template, cache_key)
    try:
        render_ms = await _render(template, cache_key, output_path)
    except Exception as e:
        logger.exception(f'Render failed for {poster_type}/{cache_key}: {e}')
        # On failure: if a stale-but-existent cache row points at a real file,
        # serve that as fallback rather than 5xx-ing the consumer.
        if row and row.get('file_path') and Path(row['file_path']).exists():
            logger.warning(f'Serving stale cache for {poster_type}/{cache_key} after render failure')
            return Path(row['file_path'])
        raise

    data_hash = compute_data_hash(poster_type, cache_key) or ''
    _cache_write(
        poster_type=poster_type,
        cache_key=cache_key,
        template_version=template.version,
        data_hash=data_hash,
        file_path=str(output_path),
        render_ms=render_ms,
    )
    return output_path


def force_refresh(poster_type: str, cache_key: str) -> bool:
    """Drop cache for (type, key) so the next request renders fresh.

    Called by the manual /refresh endpoint and by event-driven invalidation
    hooks in routes/approvals.py and routes/regions.py.
    """
    return invalidate(poster_type, cache_key)


def cache_stats() -> dict:
    """Return aggregate stats for the admin queue UI."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT poster_type, COUNT(*) as cnt,
                   AVG(render_ms) as avg_ms,
                   MAX(generated_at) as latest
            FROM poster_cache
            GROUP BY poster_type
        ''')
        per_type = [dict(r) for r in cursor.fetchall()]
        cursor.execute('SELECT COUNT(*) as total FROM poster_cache')
        total = cursor.fetchone()['total']
    return {
        'browser_ready': is_browser_ready(),
        'render_concurrency': RENDER_CONCURRENCY,
        'render_timeout_s': RENDER_TIMEOUT_S,
        'total_cached': total,
        'per_type': per_type,
        'registry': list_templates(),
    }


# ============================================================================
# Startup pre-warm — render the posters a first-time visitor sees by default
# (Normal reality, no filters, first page at each browse level) so they hit
# the cache instead of a cold render the moment they land on the page.
#
# Budget — 100 of each type (300 total):
#   * 100 atlas_thumb  — top galaxies in Normal by system_count
#   * 100 region_thumb — top regions in Euclid+Normal (matches /api/regions
#                         /grouped default ordering: Sea of Gidzenuf pin,
#                         then named, then unnamed; ties by system_count DESC)
#   * 100 system_thumb — first 100 systems of the TOP region in Euclid+Normal,
#                         ordered by created_at DESC (matches /api/systems
#                         default ordering and L4 'recent-desc' default sort)
#
# Sequence matters less than total wall time — get_or_render() skips fresh
# cache entries, so a restart that finds everything still fresh costs only
# the SQL queries below (~few ms).
# ============================================================================

PREWARM_GALAXIES_LIMIT = 100
PREWARM_REGIONS_LIMIT = 100
PREWARM_SYSTEMS_LIMIT = 100


def _prewarm_targets() -> list[tuple[str, str]]:
    """Return the ordered list of (poster_type, cache_key) to pre-render.

    Built entirely from indexed SQL — no extractor / approval coupling, just
    a snapshot of "what the default-view user sees on page 1 of each level".
    """
    targets: list[tuple[str, str]] = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # L2 — top galaxies in Normal reality by system count. Mirrors
            # /api/galaxies/summary's ORDER BY system_count DESC.
            cursor.execute('''
                SELECT COALESCE(s.galaxy, 'Euclid') as galaxy,
                       COUNT(*) as system_count
                FROM systems s
                WHERE COALESCE(s.reality, 'Normal') = 'Normal'
                GROUP BY COALESCE(s.galaxy, 'Euclid')
                ORDER BY system_count DESC
                LIMIT ?
            ''', (PREWARM_GALAXIES_LIMIT,))
            for row in cursor.fetchall():
                galaxy = row['galaxy']
                if galaxy:
                    targets.append(('atlas_thumb', galaxy))

            # L3 — top regions in Euclid+Normal. Mirrors /api/regions/grouped
            # ORDER BY: Sea of Gidzenuf pin first, then named, then unnamed,
            # ties broken by system_count DESC.
            cursor.execute('''
                SELECT s.region_x, s.region_y, s.region_z,
                       r.custom_name,
                       COUNT(DISTINCT s.id) as system_count,
                       MIN(s.created_at) as first_system_date,
                       MIN(s.id) as first_system_id
                FROM systems s
                LEFT JOIN regions r ON s.region_x = r.region_x
                    AND s.region_y = r.region_y AND s.region_z = r.region_z
                WHERE s.region_x IS NOT NULL
                  AND s.region_y IS NOT NULL
                  AND s.region_z IS NOT NULL
                  AND COALESCE(s.reality, 'Normal') = 'Normal'
                  AND COALESCE(s.galaxy, 'Euclid') = 'Euclid'
                GROUP BY s.region_x, s.region_y, s.region_z
                ORDER BY
                    CASE
                        WHEN r.custom_name = 'Sea of Gidzenuf' THEN 0
                        WHEN r.custom_name IS NOT NULL THEN 1
                        ELSE 2
                    END ASC,
                    system_count DESC,
                    first_system_date ASC,
                    first_system_id ASC
                LIMIT ?
            ''', (PREWARM_REGIONS_LIMIT,))
            region_rows = cursor.fetchall()
            for row in region_rows:
                key = f"{row['region_x']}_{row['region_y']}_{row['region_z']}"
                targets.append(('region_thumb', key))

            # L4 — first page of systems in the TOP region of Euclid+Normal,
            # ordered to match /api/systems' `ORDER BY created_at DESC NULLS
            # LAST, id DESC` and the frontend's 'recent-desc' default sort.
            if region_rows:
                top = region_rows[0]
                cursor.execute('''
                    SELECT s.id
                    FROM systems s
                    WHERE s.region_x = ?
                      AND s.region_y = ?
                      AND s.region_z = ?
                      AND COALESCE(s.reality, 'Normal') = 'Normal'
                      AND COALESCE(s.galaxy, 'Euclid') = 'Euclid'
                    ORDER BY s.created_at DESC, s.id DESC
                    LIMIT ?
                ''', (top['region_x'], top['region_y'], top['region_z'], PREWARM_SYSTEMS_LIMIT))
                for row in cursor.fetchall():
                    targets.append(('system_thumb', str(row['id'])))
    except Exception as e:
        logger.warning(f'Pre-warm target query failed: {e}')
        return []

    return targets


async def _prewarm_one(poster_type: str, cache_key: str) -> tuple[str, bool, Optional[str]]:
    """Render or confirm-cached one (type, key). Returns (label, was_cached, error)."""
    label = f'{poster_type}/{cache_key}'
    try:
        row = _cache_lookup(poster_type, cache_key)
        if row and is_cache_fresh(poster_type, cache_key, row):
            return label, True, None
        await get_or_render(poster_type, cache_key)
        return label, False, None
    except Exception as e:
        return label, False, str(e)


async def prewarm_default_posters() -> None:
    """Background pre-warm of the default-browse posters.

    Scheduled from the FastAPI startup lifespan after init_browser() returns.

    Worker-pool pattern — the previous `asyncio.gather([_prewarm_one(...) for
    ...])` dispatched all 300 targets at once. Each task entered _render()
    and waited on the 4-slot semaphore; the 300th task waited 60-90s in the
    queue before its own work started, and that wait inflated render_ms in
    the cache (Parker reported "60-90s renders" 2026-05-13 — the actual
    Chromium work was 1-2s, the rest was queue time).

    Instead, we run PREWARM_WORKERS (= max(1, RENDER_CONCURRENCY-1)) workers
    that pull from an asyncio.Queue. That bounds in-flight prewarm work
    *and* leaves at least one semaphore slot free for live user requests —
    when someone navigates while pre-warm is still running, their poster
    request can always grab a slot instead of waiting behind the prewarm.
    """
    if not is_browser_ready():
        logger.warning('Poster pre-warm: browser not ready, skipping')
        return

    targets = _prewarm_targets()
    if not targets:
        logger.info('Poster pre-warm: no targets (empty DB?)')
        return

    by_type: dict[str, int] = {}
    for t, _ in targets:
        by_type[t] = by_type.get(t, 0) + 1
    summary = ', '.join(f'{n} {t}' for t, n in by_type.items())
    workers = max(1, RENDER_CONCURRENCY - 1)
    logger.info(
        f'Poster pre-warm: starting on {len(targets)} targets ({summary}) '
        f'with {workers} concurrent workers'
    )

    queue: asyncio.Queue = asyncio.Queue()
    for t, k in targets:
        queue.put_nowait((t, k))

    results: list[tuple[str, bool, Optional[str]]] = []
    rendered_counter = {'n': 0}
    progress_total = len(targets)

    async def _worker():
        while True:
            try:
                poster_type, cache_key = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                res = await _prewarm_one(poster_type, cache_key)
            except Exception as e:
                res = (f'{poster_type}/{cache_key}', False, str(e))
            results.append(res)
            rendered_counter['n'] += 1
            # Per-100 progress beat so the operator sees prewarm ticking
            # without per-poster log spam.
            if rendered_counter['n'] % 100 == 0:
                logger.info(
                    f'Poster pre-warm: {rendered_counter["n"]}/{progress_total} done'
                )
            queue.task_done()

    start = time.monotonic()
    await asyncio.gather(*[_worker() for _ in range(workers)])
    elapsed_s = int(time.monotonic() - start)

    rendered = sum(1 for _, was_cached, err in results if not was_cached and err is None)
    cached = sum(1 for _, was_cached, err in results if was_cached)
    failed = [(label, err) for label, _, err in results if err is not None]

    logger.info(
        f'Poster pre-warm: done in {elapsed_s}s — rendered={rendered}, '
        f'already-cached={cached}, failed={len(failed)}'
    )
    if failed:
        # Cap at 5 to keep the startup log readable
        for label, err in failed[:5]:
            logger.warning(f'Poster pre-warm: {label} failed: {err}')


def prune_old_cache_rows(days: int = CACHE_PRUNE_AFTER_DAYS) -> int:
    """Drop cache rows older than `days` whose files haven't been re-requested.

    Called by the weekly cron. Returns the number of rows pruned.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT file_path FROM poster_cache WHERE generated_at < ?', (cutoff,))
        files_to_remove = [r['file_path'] for r in cursor.fetchall() if r['file_path']]
        cursor.execute('DELETE FROM poster_cache WHERE generated_at < ?', (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
    for fp in files_to_remove:
        try:
            p = Path(fp)
            if p.exists():
                p.unlink()
        except Exception:
            pass
    logger.info(f'Poster prune: dropped {deleted} cache rows older than {days} days')
    return deleted
