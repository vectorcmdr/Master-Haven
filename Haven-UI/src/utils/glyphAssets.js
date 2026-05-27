// Single source of truth for NMS portal glyph art + names.
//
// Art lives in src/assets/glyphs/{0-F}.webp — the transparent mint-on-clear
// set designed for the Summer Unification Day festival site. These replaced
// the older opaque IMG_92xx.webp photos that were served from the user-photos
// volume (/haven-ui-photos/) and were NOT committed to git (photos/* is
// .gitignored), so they couldn't be relied on across deploys.
//
// They are resolved through Vite's bundler (import.meta.glob with ?url) rather
// than a static public/ path on purpose: the backend's /haven-ui catch-all
// returns 404 for any *.webp not under /haven-ui/assets/ (control_room_api.py
// spa_catchall), so a public/glyphs/*.webp path would 404 in production even
// though it works in the dev server. Going through the bundler emits each
// glyph into dist/assets/ (or inlines it as a data URI when small), and the
// URL is correct in dev, prod, and inside the Playwright-rendered poster
// pages alike.

export const HEX_DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'];

export const GLYPH_NAMES = {
  '0': 'Sunset', '1': 'Bird', '2': 'Face', '3': 'Diplo',
  '4': 'Eclipse', '5': 'Balloon', '6': 'Boat', '7': 'Bug',
  '8': 'Dragonfly', '9': 'Galaxy', 'A': 'Voxel', 'B': 'Fish',
  'C': 'Tent', 'D': 'Rocket', 'E': 'Tree', 'F': 'Atlas',
};

// Eagerly import every glyph as a resolved URL (bundler-emitted or inlined).
// Keys look like '../assets/glyphs/0.webp'; values are the served URLs.
const _glyphModules = import.meta.glob('../assets/glyphs/*.webp', {
  eager: true,
  query: '?url',
  import: 'default',
});

const GLYPH_SRC = {};
for (const [path, url] of Object.entries(_glyphModules)) {
  const m = path.match(/\/([0-9A-Fa-f])\.webp$/);
  if (m) GLYPH_SRC[m[1].toUpperCase()] = url;
}

// Returns the served URL for a single hex glyph (0-9, A-F), or null if the
// digit isn't a valid glyph symbol.
export function glyphImageSrc(digit) {
  if (digit == null) return null;
  return GLYPH_SRC[String(digit).toUpperCase()] || null;
}

export function glyphName(digit) {
  if (digit == null) return '';
  return GLYPH_NAMES[String(digit).toUpperCase()] || '';
}
