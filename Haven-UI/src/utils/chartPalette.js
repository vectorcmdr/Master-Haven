/**
 * Chart color palette — single source for Recharts colors across the app.
 *
 * Pre-2.0, every chart page (Analytics, PartnerAnalytics, CommunityStats)
 * hardcoded #06b6d4 (cyan) and #a855f7 (purple) inline. None of those
 * matched the canonical brand colors --app-primary (#00C2B3) and
 * --app-accent-2 (#9d4edd). Introduced via the 2.0 audit rollout plan,
 * 2026-05-16.
 *
 * Recharts can't read CSS variables directly (it needs concrete strings),
 * so the brand-correct hex values are mirrored here. Keep these in sync
 * with the tokens in styles/index.css :root:
 *   manual         ↔  --app-primary       (#00C2B3)
 *   extractor      ↔  --app-accent-2      (#9d4edd)
 *   discovery      ↔  --app-accent-amber  (#ffb44c)
 *   success        ↔  emerald-400         (#34d399)  — matches .grade-a / .pill-emerald
 *   warning        ↔  amber-400           (#fbbf24)
 *   danger         ↔  red-400             (#f87171)
 *   info           ↔  blue-400            (#60a5fa)  — matches .grade-b
 *   muted          ↔  white-25            (rgba(255,255,255,0.25)) — matches .bar-c
 */
export const CHART_PALETTE = {
  manual:    '#00C2B3',
  extractor: '#9d4edd',
  discovery: '#ffb44c',
  success:   '#34d399',
  warning:   '#fbbf24',
  danger:    '#f87171',
  info:      '#60a5fa',
  muted:     'rgba(255, 255, 255, 0.45)',
}

/**
 * Discovery-type colors — used by CommunityStats's discovery breakdown,
 * the Discoveries hub, and any other view that categorises by discovery
 * type. Picked to be reasonably distinct on the dark theme.
 */
export const DISCOVERY_TYPE_PALETTE = {
  fauna:     '#34d399',  // emerald
  flora:     '#86efac',  // light green
  mineral:   '#fbbf24',  // amber
  ruin:      '#d4a3ff',  // purple-light
  anomaly:   '#60a5fa',  // blue
  base:      '#00C2B3',  // teal (brand)
  multitool: '#f472b6',  // pink
  ship:      '#fb923c',  // orange
  freighter: '#a78bfa',  // purple
  other:     'rgba(255, 255, 255, 0.45)',
}

/**
 * Resolve a discovery type to its palette color, falling back to "other".
 */
export function colorForDiscoveryType(type) {
  if (!type) return DISCOVERY_TYPE_PALETTE.other
  return DISCOVERY_TYPE_PALETTE[type.toLowerCase()] || DISCOVERY_TYPE_PALETTE.other
}
