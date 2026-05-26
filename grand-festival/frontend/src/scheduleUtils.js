// Shared helpers for turning the live schedule (from the Google Sheet) into the
// real activity list. Used by both the homepage highlights and Who's Going.

// A value is "real" only if non-empty and not a TBA/TBD/TBC placeholder.
export const realText = (t) => {
  const v = (t || '').trim()
  return v && !/^(tba|tbd|tbc)$/i.test(v) ? v : null
}
export const realLoc = realText

// Distinct activities people committed to, in schedule order. Includes the
// festival opening and reserved-but-unspecified slots (e.g. NMSCord "TBA");
// skips hosts with a completely blank Event cell (just a reserved time).
export function deriveActivities(days) {
  const out = []
  const seen = new Set()
  for (const day of days || []) {
    for (const item of day.items || []) {
      const host = (item.host || '').trim()
      const event = realText(item.event)
      const reserved = (item.event || '').trim() !== '' || /open/i.test(host)
      if (!host || !reserved) continue
      const key = `${host}||${event || ''}`.toLowerCase()
      if (seen.has(key)) continue
      seen.add(key)
      out.push({ host, event, location: item.location })
    }
  }
  return out
}

// A festival emoji picked from the activity's wording.
export function activityIcon({ host, event }) {
  const s = `${event || ''} ${host || ''}`.toLowerCase()
  if (/open/.test(s)) return '🎆'
  if (/egg/.test(s)) return '🥚'
  if (/pvp|battle|combat|arena/.test(s)) return '⚔️'
  if (/bak/.test(s)) return '🧁'
  if (/rac|pulse/.test(s)) return '🏁'
  if (/cruise|corvette/.test(s)) return '🚀'
  if (/tea|cafe|lounge/.test(s)) return '🫖'
  if (/castle|nexus|city|showcase|show|build|hub|community|festival/.test(s)) return '🏛️'
  return '🎉'
}

// Short supporting line for a card.
export function activityNote({ host, event }) {
  if (event) return `Hosted by ${host}`
  if (/open/i.test(host)) return 'Festival opening'
  return 'Details to be announced'
}
