import GlyphStrip from './GlyphStrip.jsx'
import { realLoc } from '../scheduleUtils.js'

// One creator entry — name, optional event, optional day+time chip, optional
// portal coords, and a follow-link to whatever they put in column J of the
// sheet (Twitch / YouTube / X / their own Discord, etc.).
export default function CreatorCard({ creator }) {
  const { host, event, day, location, link } = creator
  const dayShort = (day || '').replace(/^Festival\s+/i, '').replace(/^Day\s*/i, 'Day ')

  return (
    <div className="creator-card">
      <div className="creator-head">
        <h3 className="creator-host">{host || 'Creator'}</h3>
        <div className="badge creator-badge">Creator</div>
      </div>
      {event && <p className="creator-event">{event}</p>}

      {dayShort && (
        <div className="creator-when">
          <span className="creator-day">{dayShort}</span>
        </div>
      )}

      {realLoc(location) && (
        <div className="creator-loc">
          <GlyphStrip code={location.trim()} size="sm" />
        </div>
      )}

      {link && /^https?:\/\//i.test(link) && (
        <a className="creator-link" href={link} target="_blank" rel="noopener noreferrer">
          <span aria-hidden="true">▸</span> Follow / watch
        </a>
      )}
    </div>
  )
}
