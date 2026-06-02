import React from 'react'

/**
 * Surface-coordinate input for discoveries — two decimal fields (latitude,
 * longitude) plus paste-parse: pasting a combined "+45.23, -12.85" string
 * into either field auto-splits it across both. Mirrors the lat/long NMS
 * shows in the analysis visor.
 *
 * Controlled: values are kept as strings by the parent (so a half-typed
 * "-" or "12." stays editable); parse to float at submit time. Range:
 * latitude [-90, 90], longitude [-180, 180]. An out-of-range value renders
 * an inline error but is NOT mutated — the parent decides whether to block.
 *
 * Props:
 *   latitude, longitude  string|number|null — current values
 *   onChange(lat, lng)   called with the two raw strings on any edit
 *   disabled             bool — greys out + ignores input (e.g. space discoveries)
 */
export default function LatLngInput({ latitude, longitude, onChange, disabled = false }) {
  const latStr = latitude === null || latitude === undefined ? '' : String(latitude)
  const lngStr = longitude === null || longitude === undefined ? '' : String(longitude)

  const inRange = (v, limit) => {
    if (v === '' || v === '-' || v === '+' || v === '.') return true // mid-typing
    const f = parseFloat(v)
    return !Number.isNaN(f) && f >= -limit && f <= limit
  }
  const latBad = !inRange(latStr, 90)
  const lngBad = !inRange(lngStr, 180)

  // Pull two numbers out of a pasted "lat, lng" / "lat lng" / "lat / lng" blob.
  const parsePair = (text) => {
    const nums = String(text).match(/-?\d+(?:\.\d+)?/g)
    if (nums && nums.length >= 2) return [nums[0], nums[1]]
    return null
  }

  const handlePaste = (which) => (e) => {
    if (disabled) return
    const text = e.clipboardData?.getData('text') || ''
    const pair = parsePair(text)
    if (pair) {
      e.preventDefault()
      onChange(pair[0], pair[1])
    }
    // single value pasted → let the default paste land in the focused field
  }

  const inputStyle = {
    backgroundColor: 'var(--app-bg)',
    border: '1px solid var(--app-accent-3)',
    opacity: disabled ? 0.5 : 1,
  }

  return (
    <div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs muted mb-1">Latitude</label>
          <input
            type="text"
            inputMode="decimal"
            className="w-full p-2 rounded"
            style={{ ...inputStyle, borderColor: latBad ? 'var(--app-accent-amber)' : 'var(--app-accent-3)' }}
            value={latStr}
            disabled={disabled}
            onChange={e => onChange(e.target.value, lngStr)}
            onPaste={handlePaste('lat')}
            placeholder="+45.23"
          />
        </div>
        <div>
          <label className="block text-xs muted mb-1">Longitude</label>
          <input
            type="text"
            inputMode="decimal"
            className="w-full p-2 rounded"
            style={{ ...inputStyle, borderColor: lngBad ? 'var(--app-accent-amber)' : 'var(--app-accent-3)' }}
            value={lngStr}
            disabled={disabled}
            onChange={e => onChange(latStr, e.target.value)}
            onPaste={handlePaste('lng')}
            placeholder="-12.85"
          />
        </div>
      </div>
      {(latBad || lngBad) && (
        <div className="text-xs mt-1" style={{ color: 'var(--app-accent-amber)' }}>
          {latBad && 'Latitude must be between -90 and 90. '}
          {lngBad && 'Longitude must be between -180 and 180.'}
        </div>
      )}
      <div className="text-xs muted mt-1">
        Optional — the surface coordinates NMS shows in the analysis visor. Paste “lat, long” into either box to fill both.
      </div>
    </div>
  )
}

/** True when a string value is a valid coordinate (or empty). Shared by callers. */
export function coordValid(value, limit) {
  if (value === '' || value === null || value === undefined) return true
  const f = parseFloat(value)
  return !Number.isNaN(f) && f >= -limit && f <= limit
}

/** Coerce a coordinate string to a float or null (for payload building). */
export function coordToFloat(value) {
  if (value === '' || value === null || value === undefined) return null
  const f = parseFloat(value)
  return Number.isNaN(f) ? null : f
}

/**
 * Format a lat/long pair for display, e.g. "+45.23, -12.85". Returns null
 * when either value is missing/non-numeric so callers can skip rendering.
 */
export function formatCoords(latitude, longitude) {
  const lat = coordToFloat(latitude)
  const lng = coordToFloat(longitude)
  if (lat === null || lng === null) return null
  const fmt = (n) => (n >= 0 ? '+' : '') + n.toFixed(2)
  return `${fmt(lat)}, ${fmt(lng)}`
}
