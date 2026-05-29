import { useCallback, useEffect, useState } from 'react'
import DiscordLink from '../components/DiscordLink.jsx'
import {
  adminApprove,
  adminClearLogo,
  adminCreateCreator,
  adminDelete,
  adminDeleteCreator,
  adminEdit,
  adminEditCreator,
  adminListCivs,
  adminListCreators,
  adminLog,
  adminLogin,
  adminLogout,
  adminMe,
  adminReject,
  adminRestoreCreator,
  adminSetLogo,
} from '../api.js'

const STATUS_LABEL = { host: '★ Host', confirmed: 'Confirmed', tentative: 'Tentative' }

function LoginForm({ onLogin }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await adminLogin(password)
      onLogin()
    } catch (err) {
      setError(err.status === 401 ? 'Incorrect password.' : err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="page active">
      <section className="signup-hero">
        <h1>Organizer Access</h1>
        <p>Sign in to review civilization submissions.</p>
      </section>
      <section className="signup-body">
        <div className="signup-inner" style={{ gridTemplateColumns: '1fr', maxWidth: 480 }}>
          <div className="signup-card">
            <form className="civ-form" onSubmit={submit}>
              <h2>Admin login</h2>
              <label className="field">
                <span>Password</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                />
              </label>
              {error && <div className="state-msg error">{error}</div>}
              <button className="hero-cta submit-btn" type="submit" disabled={busy}>
                {busy ? 'Signing in…' : 'Sign in ▸'}
              </button>
            </form>
          </div>
        </div>
      </section>
    </main>
  )
}

function AdminCivRow({ civ, onChanged, onError }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(civ)
  const [busy, setBusy] = useState(false)

  const run = async (fn) => {
    setBusy(true)
    onError(null)
    try {
      await fn()
      await onChanged()
    } catch (err) {
      onError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const startEdit = () => {
    setDraft(civ)
    setEditing(true)
  }

  const save = () =>
    run(async () => {
      await adminEdit(civ.id, {
        name: draft.name,
        role: draft.role,
        description: draft.description,
        status: draft.status,
        discord_link: (draft.discord_link || '').trim(),
        display_order: Number(draft.display_order) || 0,
      })
      setEditing(false)
    })

  const reject = () => {
    const notes = window.prompt('Optional reason for rejecting (visible only in the audit log):', '')
    if (notes === null) return // cancelled
    run(() => adminReject(civ.id, notes))
  }

  const del = () => {
    if (!window.confirm(`Delete "${civ.name}"? This cannot be undone.`)) return
    run(() => adminDelete(civ.id))
  }

  const setField = (k) => (e) => setDraft((d) => ({ ...d, [k]: e.target.value }))

  const [logoErr, setLogoErr] = useState(null)
  const onLogo = (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-selecting the same file later
    if (!file) return
    setLogoErr(null)
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      setLogoErr('Use a PNG, JPEG, or WebP image.')
      return
    }
    if (file.size > 2 * 1024 * 1024) {
      setLogoErr('Image must be under 2 MB.')
      return
    }
    run(() => adminSetLogo(civ.id, file))
  }
  const removeLogo = () => {
    setLogoErr(null)
    run(() => adminClearLogo(civ.id))
  }

  return (
    <div className={`admin-card admin-card-${civ.approval_state}`}>
      <div className="admin-card-head">
        {civ.logo_url && <img className="admin-logo" src={civ.logo_url} alt="" />}
        <div className="admin-card-titles">
          {editing ? (
            <input className="admin-inline" value={draft.name} onChange={setField('name')} />
          ) : (
            <h4>{civ.name}</h4>
          )}
          {editing ? (
            <input className="admin-inline" value={draft.role} onChange={setField('role')} />
          ) : (
            <div className="admin-role">{civ.role}</div>
          )}
        </div>
        <span className={`badge ${civ.status}`}>{STATUS_LABEL[civ.status] || civ.status}</span>
      </div>

      {editing ? (
        <textarea className="admin-inline" rows={3} value={draft.description} onChange={setField('description')} />
      ) : (
        <p className="admin-desc">{civ.description}</p>
      )}

      {!editing && civ.discord_link && (
        <div style={{ marginTop: '0.2rem' }}>
          <DiscordLink url={civ.discord_link} />
        </div>
      )}

      {editing && (
        <>
          <label className="admin-field-label">
            Discord link
            <input
              className="admin-inline"
              type="url"
              value={draft.discord_link || ''}
              onChange={setField('discord_link')}
              placeholder="https://discord.gg/..."
            />
          </label>
          <div className="admin-edit-row">
            <label>
              Status
              <select value={draft.status} onChange={setField('status')}>
                <option value="host">Host</option>
                <option value="confirmed">Confirmed</option>
                <option value="tentative">Tentative</option>
              </select>
            </label>
            <label>
              Display order
              <input type="number" value={draft.display_order ?? 100} onChange={setField('display_order')} />
            </label>
          </div>
        </>
      )}

      {(civ.submitter_discord || civ.submitter_notes) && !editing && (
        <div className="admin-submitter">
          {civ.submitter_discord && (
            <div><span className="admin-label">Submitter</span> {civ.submitter_discord}</div>
          )}
          {civ.submitter_notes && (
            <div><span className="admin-label">Notes</span> {civ.submitter_notes}</div>
          )}
        </div>
      )}

      <div className="admin-logo-row">
        <span className="admin-label">Emblem</span>
        {civ.logo_url ? (
          <img className="admin-logo-thumb" src={civ.logo_url} alt={`${civ.name} emblem`} />
        ) : (
          <span className="admin-logo-none">none yet</span>
        )}
        <label className={`btn btn-ghost btn-file ${busy ? 'btn-disabled' : ''}`}>
          {civ.logo_url ? 'Replace' : 'Upload'}
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={onLogo} disabled={busy} hidden />
        </label>
        {civ.logo_url && (
          <button className="btn btn-danger" onClick={removeLogo} disabled={busy}>Remove</button>
        )}
        {logoErr && <span className="field-error">{logoErr}</span>}
      </div>

      <div className="admin-actions">
        {editing ? (
          <>
            <button className="btn btn-approve" onClick={save} disabled={busy}>Save</button>
            <button className="btn btn-ghost" onClick={() => setEditing(false)} disabled={busy}>Cancel</button>
          </>
        ) : (
          <>
            {civ.approval_state !== 'approved' && (
              <button className="btn btn-approve" onClick={() => run(() => adminApprove(civ.id))} disabled={busy}>
                Approve
              </button>
            )}
            {civ.approval_state !== 'rejected' && (
              <button className="btn btn-reject" onClick={reject} disabled={busy}>Reject</button>
            )}
            <button className="btn btn-ghost" onClick={startEdit} disabled={busy}>Edit</button>
            <button className="btn btn-danger" onClick={del} disabled={busy}>Delete</button>
          </>
        )}
      </div>
    </div>
  )
}

// --- Creator Corner admin ---------------------------------------------------

const CREATOR_FIELDS = [
  ['host', 'Creator name'],
  ['event', 'What they\'re bringing'],
  ['day', 'Day (e.g. "Festival Day 1: Friday, 19 June 2026")'],
  ['location', 'Portal hex'],
  ['link', 'Link (Twitch / YouTube / X / etc.)'],
  ['notes', 'Admin notes (private)'],
]

function AdminCreatorRow({ creator, onChanged, onError }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(creator)
  const [busy, setBusy] = useState(false)

  const run = async (fn) => {
    setBusy(true)
    onError(null)
    try {
      await fn()
      await onChanged()
    } catch (err) {
      onError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const startEdit = () => {
    setDraft(creator)
    setEditing(true)
  }
  const save = () =>
    run(async () => {
      const patch = {}
      for (const [k] of CREATOR_FIELDS) if (draft[k] !== creator[k]) patch[k] = draft[k] || ''
      if (Object.keys(patch).length === 0) {
        setEditing(false)
        return
      }
      await adminEditCreator(creator.id, patch)
      setEditing(false)
    })
  const toggleHidden = () =>
    run(() => adminEditCreator(creator.id, { hidden: creator.hidden ? 0 : 1 }))
  const restore = () => {
    if (!window.confirm(
      creator.from_sheet
        ? 'Drop your edits and re-pull this row from the sheet?'
        : 'This is an admin-only row — restoring will DELETE it. Continue?',
    )) return
    run(() => adminRestoreCreator(creator.id))
  }
  const del = () => {
    if (!window.confirm(`Delete "${creator.host}"? Sheet-sourced rows will return on next sync.`)) return
    run(() => adminDeleteCreator(creator.id))
  }

  return (
    <div className={`admin-civ admin-creator ${creator.hidden ? 'is-hidden' : ''}`}>
      <div className="admin-civ-head">
        <div>
          {editing ? (
            <input
              className="admin-edit-input"
              value={draft.host || ''}
              onChange={(e) => setDraft({ ...draft, host: e.target.value })}
              placeholder="Creator name"
            />
          ) : (
            <div className="admin-civ-name">{creator.host || <em>(no name)</em>}</div>
          )}
          <div className="admin-civ-meta">
            <span className={`badge ${creator.from_sheet ? 'host' : 'tentative'}`}>
              {creator.from_sheet ? 'From sheet' : 'Admin-only'}
            </span>
            {creator.admin_edited && <span className="badge confirmed">Edited</span>}
            {creator.hidden && <span className="badge tentative">Hidden</span>}
          </div>
        </div>
      </div>

      {editing ? (
        <div className="admin-creator-grid">
          {CREATOR_FIELDS.slice(1).map(([k, label]) => (
            <label className="field" key={k}>
              <span>{label}</span>
              {k === 'notes' ? (
                <textarea
                  rows={2}
                  value={draft[k] || ''}
                  onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
                />
              ) : (
                <input
                  value={draft[k] || ''}
                  onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
                  placeholder={label}
                />
              )}
            </label>
          ))}
        </div>
      ) : (
        <div className="admin-creator-readout">
          {creator.event && <div><span className="admin-label">Bringing</span> {creator.event}</div>}
          {creator.day && <div><span className="admin-label">Day</span> {creator.day}</div>}
          {creator.location && <div><span className="admin-label">Portal</span> <code>{creator.location}</code></div>}
          {creator.link && (
            <div>
              <span className="admin-label">Link</span>{' '}
              <a href={creator.link} target="_blank" rel="noopener noreferrer">{creator.link}</a>
            </div>
          )}
          {creator.notes && <div><span className="admin-label">Notes</span> {creator.notes}</div>}
        </div>
      )}

      <div className="admin-actions">
        {editing ? (
          <>
            <button className="btn btn-approve" onClick={save} disabled={busy}>Save</button>
            <button className="btn btn-ghost" onClick={() => setEditing(false)} disabled={busy}>Cancel</button>
          </>
        ) : (
          <>
            <button className="btn btn-ghost" onClick={startEdit} disabled={busy}>Edit</button>
            <button className="btn btn-ghost" onClick={toggleHidden} disabled={busy}>
              {creator.hidden ? 'Unhide' : 'Hide from site'}
            </button>
            {(creator.admin_edited || !creator.from_sheet) && (
              <button className="btn btn-ghost" onClick={restore} disabled={busy}>
                {creator.from_sheet ? 'Restore from sheet' : 'Discard'}
              </button>
            )}
            <button className="btn btn-danger" onClick={del} disabled={busy}>Delete</button>
          </>
        )}
      </div>
    </div>
  )
}

function AdminCreatorAdd({ onChanged, onError }) {
  const empty = { host: '', event: '', day: '', gmt: '', est: '', pst: '', aest: '', location: '', link: '', notes: '' }
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(empty)
  const [busy, setBusy] = useState(false)

  const create = async () => {
    if (!draft.host.trim()) {
      onError('Creator name is required.')
      return
    }
    setBusy(true)
    onError(null)
    try {
      await adminCreateCreator(draft)
      await onChanged()
      setDraft(empty)
      setOpen(false)
    } catch (err) {
      onError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button className="btn btn-approve" onClick={() => setOpen(true)}>
        + Add creator (admin-only)
      </button>
    )
  }

  return (
    <div className="admin-civ admin-creator">
      <div className="admin-civ-head">
        <div className="admin-civ-name">New creator (admin-only — won't appear in the sheet)</div>
      </div>
      <div className="admin-creator-grid">
        {CREATOR_FIELDS.map(([k, label]) => (
          <label className="field" key={k}>
            <span>{label}</span>
            {k === 'notes' ? (
              <textarea
                rows={2}
                value={draft[k] || ''}
                onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
              />
            ) : (
              <input
                value={draft[k] || ''}
                onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
                placeholder={label}
              />
            )}
          </label>
        ))}
      </div>
      <div className="admin-actions">
        <button className="btn btn-approve" onClick={create} disabled={busy}>
          {busy ? 'Adding…' : 'Add creator'}
        </button>
        <button className="btn btn-ghost" onClick={() => { setOpen(false); setDraft(empty) }} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function Section({ title, count, children }) {
  return (
    <div className="admin-section">
      <h3 className="admin-section-title">
        {title} {typeof count === 'number' && <span className="admin-count">{count}</span>}
      </h3>
      {children}
    </div>
  )
}

export default function Admin() {
  const [authed, setAuthed] = useState(null) // null = unknown
  const [data, setData] = useState(null)
  const [creatorsData, setCreatorsData] = useState(null)
  const [log, setLog] = useState([])
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    const [civsResp, creatorsResp, logResp] = await Promise.all([
      adminListCivs(),
      adminListCreators(),
      adminLog(),
    ])
    setData(civsResp)
    setCreatorsData(creatorsResp)
    setLog(logResp.log || [])
  }, [])

  useEffect(() => {
    adminMe()
      .then(() => setAuthed(true))
      .catch(() => setAuthed(false))
  }, [])

  useEffect(() => {
    if (authed) load().catch((e) => setError(e.message))
  }, [authed, load])

  const refresh = useCallback(() => load().catch((e) => setError(e.message)), [load])

  const logout = async () => {
    try {
      await adminLogout()
    } catch {
      /* ignore */
    }
    setAuthed(false)
    setData(null)
  }

  if (authed === null) {
    return (
      <main className="page active">
        <div className="admin-shell">
          <div className="state-msg">Checking session…</div>
        </div>
      </main>
    )
  }
  if (!authed) return <LoginForm onLogin={() => setAuthed(true)} />

  const civs = data?.civs || []
  const pending = civs.filter((c) => c.approval_state === 'pending')
  const approved = civs.filter((c) => c.approval_state === 'approved')
  const rejected = civs.filter((c) => c.approval_state === 'rejected')

  return (
    <main className="page active">
      <div className="admin-shell">
        <div className="admin-header">
          <div>
            <h1 className="admin-title">Submission Review</h1>
            <p className="admin-sub">
              {data?.pending_count || 0} pending · {approved.length} approved · {rejected.length} rejected
            </p>
          </div>
          <div className="admin-header-actions">
            <button className="btn btn-ghost" onClick={refresh}>Refresh</button>
            <button className="btn btn-ghost" onClick={logout}>Log out</button>
          </div>
        </div>

        {error && <div className="state-msg error">{error}</div>}
        {data === null && !error && <div className="state-msg">Loading submissions…</div>}

        {data !== null && (
          <>
            <Section title="Pending review" count={pending.length}>
              {pending.length === 0 ? (
                <p className="state-msg muted">Nothing waiting — the queue is clear.</p>
              ) : (
                pending.map((c) => <AdminCivRow key={c.id} civ={c} onChanged={refresh} onError={setError} />)
              )}
            </Section>

            <Section title="Approved" count={approved.length}>
              {approved.length === 0 ? (
                <p className="state-msg muted">No approved civilizations yet.</p>
              ) : (
                approved.map((c) => <AdminCivRow key={c.id} civ={c} onChanged={refresh} onError={setError} />)
              )}
            </Section>

            <Section
              title="Creator Corner"
              count={creatorsData?.creators?.length || 0}
            >
              <p className="admin-section-note">
                Preseeded from the festival sheet's "Sponsors & Creators" tab. Editing freezes
                a row against the next sync (set <code>admin_edited = 1</code>); "Restore from
                sheet" releases it again. Admin-added rows ship as <em>admin-only</em>.
                {creatorsData?.sync_error && (
                  <span className="state-msg error" style={{ display: 'block', marginTop: 6 }}>
                    Last sync attempt failed: {creatorsData.sync_error} — serving cached values.
                  </span>
                )}
              </p>
              <AdminCreatorAdd onChanged={refresh} onError={setError} />
              {(creatorsData?.creators || []).length === 0 ? (
                <p className="state-msg muted">No creator entries yet — sheet rows will appear here as they're filled in.</p>
              ) : (
                (creatorsData.creators || []).map((c) => (
                  <AdminCreatorRow key={c.id} creator={c} onChanged={refresh} onError={setError} />
                ))
              )}
            </Section>

            {rejected.length > 0 && (
              <Section title="Rejected" count={rejected.length}>
                {rejected.map((c) => (
                  <AdminCivRow key={c.id} civ={c} onChanged={refresh} onError={setError} />
                ))}
              </Section>
            )}

            <Section title="Recent activity">
              {log.length === 0 ? (
                <p className="state-msg muted">No admin actions logged yet.</p>
              ) : (
                <ul className="admin-log">
                  {log.map((e) => (
                    <li key={e.id}>
                      <span className={`log-action log-${e.action}`}>{e.action}</span>
                      <span className="log-target">#{e.target_id}</span>
                      {e.notes && <span className="log-notes">{e.notes}</span>}
                      <span className="log-time">{e.created_at}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </>
        )}
      </div>
    </main>
  )
}
