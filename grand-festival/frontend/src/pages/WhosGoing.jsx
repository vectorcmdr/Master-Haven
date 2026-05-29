import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCivs, getCreators, getSchedule } from '../api.js'
import CivCard from '../components/CivCard.jsx'
import CreatorCard from '../components/CreatorCard.jsx'
import GlyphStrip from '../components/GlyphStrip.jsx'
import DiscordLink from '../components/DiscordLink.jsx'
import { activityNote, deriveActivities, discordByHost, normalizeHost, realLoc } from '../scheduleUtils.js'

function ScheduleItem({ item }) {
  const zones = [
    item.est && `${item.est} EST`,
    item.pst && `${item.pst} PST`,
    item.aest && `${item.aest} AEST`,
  ]
    .filter(Boolean)
    .join('  ·  ')
  const title = item.host || item.event || 'TBA'
  const sub = item.host && item.event ? item.event : ''
  return (
    <div className="sched-item">
      <div className="sched-time">
        <div className="sched-gmt">{item.gmt || 'TBA'}</div>
        <div className="sched-gmt-label">GMT</div>
      </div>
      <div className="sched-body">
        <div className="sched-title">{title}</div>
        {sub && <div className="sched-sub">{sub}</div>}
        <div className="sched-meta">
          {zones && <span className="sched-zones">{zones}</span>}
          {realLoc(item.location) && <GlyphStrip code={item.location.trim()} size="sm" />}
          <DiscordLink url={item.discord} />
        </div>
      </div>
    </div>
  )
}

export default function WhosGoing() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('civs')
  const [civs, setCivs] = useState(null) // null = loading
  const [error, setError] = useState(null)
  const [schedule, setSchedule] = useState(null) // null = loading
  const [schedErr, setSchedErr] = useState(null)
  const [creators, setCreators] = useState(null) // null = loading
  const [creatorsErr, setCreatorsErr] = useState(null)

  useEffect(() => {
    let alive = true
    getCivs()
      .then((data) => alive && setCivs(data))
      .catch((e) => alive && setError(e.message))
    getSchedule()
      .then((data) => alive && setSchedule(data))
      .catch((e) => alive && setSchedErr(e.message))
    getCreators()
      .then((data) => alive && setCreators(data))
      .catch((e) => alive && setCreatorsErr(e.message))
    return () => {
      alive = false
    }
  }, [])

  const liveDays = schedule?.days || []
  // Real activities from the sheet (festival opening + stated/reserved events;
  // fully blank slots skipped). Shared with the homepage via scheduleUtils.
  const attractions = deriveActivities(liveDays)
  // Discord links come from the schedule sheet (column I), matched to each civ
  // by host name; fall back to a civ's own discord_link if set in admin.
  const discordMap = discordByHost(liveDays)

  return (
    <main className="page active">
      <section className="wg-hero">
        <h1>Who's Going</h1>
        <div className="wg-tabs">
          <button className={`wg-tab ${tab === 'civs' ? 'active' : ''}`} onClick={() => setTab('civs')}>Civilizations</button>
          <button className={`wg-tab ${tab === 'attractions' ? 'active' : ''}`} onClick={() => setTab('attractions')}>Attractions</button>
          <button className={`wg-tab ${tab === 'creators' ? 'active' : ''}`} onClick={() => setTab('creators')}>Creator Corner</button>
          <button className={`wg-tab ${tab === 'schedule' ? 'active' : ''}`} onClick={() => setTab('schedule')}>Schedule</button>
        </div>
      </section>

      <section className="wg-body">
        <div className="wg-inner">
          {tab === 'civs' && (
            <div className="wg-pane active">
              <p className="section-sub" style={{ marginBottom: '2rem' }}>
                Updated as RSVPs come in.{' '}
                <button className="link-btn" onClick={() => navigate('/whos-going/submit')}>
                  Add your civilization →
                </button>
              </p>

              {error && <div className="state-msg error">Couldn't load the roster: {error}</div>}
              {!error && civs === null && <div className="state-msg">Loading the roster…</div>}

              {!error && civs !== null && (
                <div className="civ-grid">
                  {civs.map((c) => (
                    <CivCard
                      civ={c}
                      discordUrl={discordMap[normalizeHost(c.name)] || c.discord_link || ''}
                      key={c.id}
                    />
                  ))}
                  <div
                    className="civ-card civ-card-cta"
                    onClick={() => navigate('/whos-going/submit')}
                  >
                    <div className="badge tentative">Open Slot</div>
                    <h3>Your Civilization</h3>
                    <div className="role">— add yours —</div>
                    <p>Want your community on this list? Submit it here and an organizer will review it.</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === 'attractions' && (
            <div className="wg-pane active">
              <p className="section-sub" style={{ marginBottom: '2rem' }}>
                What each community is bringing — pulled live from the festival schedule. Hosts who
                haven't confirmed an activity yet aren't listed.
              </p>

              {schedErr && <div className="state-msg error">Couldn't load activities ({schedErr}).</div>}
              {schedule === null && !schedErr && <div className="state-msg">Loading activities…</div>}
              {schedule !== null && !schedErr && attractions.length === 0 && (
                <div className="state-msg muted">No activities confirmed yet — check back soon.</div>
              )}

              {attractions.length > 0 && (
                <div className="attr-list attractions">
                  {attractions.map((a, i) => (
                    <div className="attr-item" key={i}>
                      <div className="attr-content">
                        <h4>{a.event || a.host}</h4>
                        <p>{activityNote(a)}</p>
                        {(realLoc(a.location) || a.discord) && (
                          <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
                            {realLoc(a.location) && <GlyphStrip code={a.location.trim()} size="sm" />}
                            <DiscordLink url={a.discord} />
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'creators' && (
            <div className="wg-pane active">
              <p className="section-sub" style={{ marginBottom: '2rem' }}>
                Streamers, photographers, builders, and storytellers covering the festival —
                pulled live from the creator sheet. Pick a time slot or roam the grounds; a
                meet-and-greet booth will be open at the festival site.
              </p>

              {creatorsErr && <div className="state-msg error">Couldn't load the creators ({creatorsErr}).</div>}
              {creators === null && !creatorsErr && <div className="state-msg">Loading the creator roster…</div>}
              {creators !== null && !creatorsErr && (creators.creators || []).length === 0 && (
                <div className="state-msg muted">
                  No creators have signed up yet — check back soon, or message the organizers on
                  Discord to claim a slot.
                </div>
              )}

              {(creators?.creators || []).length > 0 && (
                <div className="creator-grid">
                  {creators.creators.map((c) => (
                    <CreatorCard creator={c} key={c.id} />
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'schedule' && (
            <div className="wg-pane active">
              <p className="section-sub" style={{ marginBottom: schedule?.main_system ? '0.8rem' : '1.6rem' }}>
                Four days under summer skies — Friday 19 to Monday 22 June 2026, peaking on the
                Solstice. Times shown in GMT · EST · PST · AEST.
              </p>
              {schedule?.main_system && (
                <div className="sched-mainsystem">
                  <span className="glyph-label">Main system</span>
                  <GlyphStrip code={schedule.main_system} />
                </div>
              )}

              {schedErr && <div className="state-msg error">Couldn't load the schedule ({schedErr}).</div>}
              {schedule === null && !schedErr && <div className="state-msg">Loading the live schedule…</div>}
              {schedule !== null && !schedErr && liveDays.length === 0 && (
                <div className="state-msg muted">No sessions scheduled yet — check back soon.</div>
              )}

              {liveDays.map((day) => (
                <div className="sched-day" key={day.label}>
                  <h3 className="sched-day-label">{day.label}</h3>
                  <div className="sched-items">
                    {day.items.map((item, i) => (
                      <ScheduleItem item={item} key={i} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  )
}
