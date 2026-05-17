import React, { useState, useEffect, useContext } from 'react'
import axios from 'axios'
import Card from '../components/Card'
import { AuthContext, FEATURES } from '../utils/AuthContext'

const TIER_LABELS = { 1: 'Super Admin', 2: 'Partner', 3: 'Sub-Admin', 4: 'Member', 5: 'Read-Only' }
// Canonical tier palette (CLAUDE.md 2.0 Design Conventions)
const TIER_PILL_CLASS = { 1: 'pill-emerald', 2: 'pill-blue', 3: 'pill-teal', 4: 'pill-purple', 5: 'pill-muted' }
const tierPill = (tier) => `pill ${TIER_PILL_CLASS[tier] || 'pill-muted'}`

const PARTNER_FEATURES = [
  { key: 'system_create', label: 'Create Systems' },
  { key: 'system_edit', label: 'Edit Systems' },
  { key: 'approvals', label: 'Approvals' },
  { key: 'batch_approvals', label: 'Batch Approvals' },
  { key: 'stats', label: 'View Statistics' },
  { key: 'settings', label: 'Theme Settings' },
  { key: 'csv_import', label: 'CSV Import' },
  { key: 'war_room', label: 'War Room' },
]

const SUB_ADMIN_FEATURES = [
  { key: 'system_create', label: 'Create Systems' },
  { key: 'system_edit', label: 'Edit Systems' },
  { key: 'approvals', label: 'Approvals' },
  { key: 'batch_approvals', label: 'Batch Approvals' },
  { key: 'stats', label: 'View Statistics' },
  { key: 'settings', label: 'Theme Settings' },
]

/** @param {Object} props @param {boolean} [props.embedded=false] When true, hides the page title row — used when mounted inside AccessControl. */
export default function UserManagement({ embedded = false }) {
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isPartner, user } = auth
  const [profiles, setProfiles] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [tierFilter, setTierFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [partners, setPartners] = useState([]) // For sub-admin parent dropdown

  // Edit modal
  const [editProfile, setEditProfile] = useState(null) // full profile detail
  const [editForm, setEditForm] = useState({})
  const [editSaving, setEditSaving] = useState(false)

  // Elevate modal
  const [elevateProfile, setElevateProfile] = useState(null)
  const [elevateForm, setElevateForm] = useState({ tier: 2, partner_discord_tag: '', enabled_features: [], parent_profile_id: null, additional_discord_tags: [], can_approve_personal_uploads: false })
  const [elevating, setElevating] = useState(false)

  // Reset password
  const [resetProfile, setResetProfile] = useState(null)
  const [resetPassword, setResetPassword] = useState('')
  const [resetting, setResetting] = useState(false)

  useEffect(() => { fetchProfiles() }, [page, search, tierFilter])
  useEffect(() => {
    if (isSuperAdmin) {
      // Fetch partner list for sub-admin parent dropdown
      axios.get('/api/admin/profiles', { params: { tier: 2, per_page: 100 } })
        .then(r => setPartners(r.data.profiles || []))
        .catch(() => {})
    }
  }, [isSuperAdmin])

  async function fetchProfiles() {
    setLoading(true)
    try {
      const params = { page, per_page: 25 }
      if (search) params.search = search
      if (tierFilter) params.tier = tierFilter
      const r = await axios.get('/api/admin/profiles', { params })
      setProfiles(r.data.profiles || [])
      setTotal(r.data.total || 0)
    } catch {
    } finally {
      setLoading(false)
    }
  }

  async function openEditModal(profile) {
    try {
      const r = await axios.get(`/api/admin/profiles/${profile.id}`)
      const detail = r.data
      setEditProfile(detail)
      setEditForm({
        display_name: detail.display_name || '',
        enabled_features: detail.enabled_features || [],
        additional_discord_tags: detail.additional_discord_tags || [],
        can_approve_personal_uploads: detail.can_approve_personal_uploads || false,
        partner_discord_tag: detail.partner_discord_tag || '',
        parent_profile_id: detail.parent_profile_id || null,
      })
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to load profile')
    }
  }

  async function saveEdit() {
    if (!editProfile) return
    setEditSaving(true)
    try {
      const body = { ...editForm }

      // If changing tier, use the tier endpoint
      if (editProfile.tier === 2 || editProfile.tier === 3) {
        // Update features and settings via the edit endpoint
        await axios.put(`/api/admin/profiles/${editProfile.id}`, {
          display_name: body.display_name,
          enabled_features: body.enabled_features,
          additional_discord_tags: body.additional_discord_tags,
          can_approve_personal_uploads: body.can_approve_personal_uploads,
        })
      }

      setEditProfile(null)
      fetchProfiles()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to save')
    } finally {
      setEditSaving(false)
    }
  }

  async function handleElevate() {
    if (!elevateProfile) return
    setElevating(true)
    try {
      await axios.put(`/api/admin/profiles/${elevateProfile.id}/tier`, elevateForm)
      setElevateProfile(null)
      fetchProfiles()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to elevate')
    } finally {
      setElevating(false)
    }
  }

  async function toggleActive(profile) {
    try {
      await axios.put(`/api/admin/profiles/${profile.id}`, { is_active: !profile.is_active })
      fetchProfiles()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update')
    }
  }

  async function handleResetPassword() {
    if (!resetProfile || resetPassword.length < 4) return
    setResetting(true)
    try {
      await axios.post(`/api/admin/profiles/${resetProfile.id}/reset-password`, { new_password: resetPassword })
      setResetProfile(null)
      setResetPassword('')
      alert('Password reset successfully')
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to reset password')
    } finally {
      setResetting(false)
    }
  }

  function toggleFeature(key) {
    setEditForm(f => ({
      ...f,
      enabled_features: f.enabled_features.includes(key)
        ? f.enabled_features.filter(k => k !== key)
        : [...f.enabled_features, key]
    }))
  }

  function toggleElevateFeature(key) {
    setElevateForm(f => ({
      ...f,
      enabled_features: f.enabled_features.includes(key)
        ? f.enabled_features.filter(k => k !== key)
        : [...f.enabled_features, key]
    }))
  }

  const totalPages = Math.ceil(total / 25)
  const canManage = isSuperAdmin || isPartner

  return (
    <div className="space-y-6">
      {!embedded && (
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">User Management</h1>
          <span className="text-sm" style={{ color: 'var(--muted)' }}>{total} profiles</span>
        </div>
      )}
      {embedded && (
        <div className="flex justify-end">
          <span className="text-sm" style={{ color: 'var(--muted)' }}>{total} profiles</span>
        </div>
      )}

      {/* Filters */}
      <Card>
        <div className="flex gap-3 flex-wrap">
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search username..."
            className="haven-input flex-1 min-w-48 p-2"
          />
          <select
            value={tierFilter}
            onChange={e => { setTierFilter(e.target.value); setPage(1) }}
            className="haven-input p-2"
          >
            <option value="">All Tiers</option>
            <option value="2">Partners</option>
            <option value="3">Sub-Admins</option>
            <option value="4">Members</option>
            <option value="5">Read-Only</option>
          </select>
        </div>
      </Card>

      {/* Profiles table */}
      <Card>
        {loading ? (
          <div className="text-center py-8" style={{ color: 'var(--muted)' }}>Loading...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left" style={{ color: 'var(--muted)', borderBottom: '1px solid var(--border-soft)' }}>
                  <th className="pb-2 pr-4">Username</th>
                  <th className="pb-2 pr-4">Tier</th>
                  <th className="pb-2 pr-4">Community</th>
                  <th className="pb-2 pr-4">Systems</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Last Login</th>
                  {canManage && <th className="pb-2">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {profiles.map(p => (
                  <tr key={p.id} style={{ borderBottom: '1px solid var(--border-soft)' }}>
                    <td className="py-2 pr-4">
                      <div className="font-medium">{p.username}</div>
                      {p.display_name && p.display_name !== p.username && (
                        <div className="text-xs" style={{ color: 'var(--muted)' }}>{p.display_name}</div>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      <span className={tierPill(p.tier)}>
                        {TIER_LABELS[p.tier] || `Tier ${p.tier}`}
                      </span>
                    </td>
                    <td className="py-2 pr-4">
                      {p.partner_discord_tag ? (
                        <span style={{ color: 'var(--app-primary)' }}>{p.partner_discord_tag}</span>
                      ) : p.default_civ_tag ? (
                        <span style={{ color: 'var(--muted)' }}>{p.default_civ_tag}</span>
                      ) : (
                        <span style={{ color: 'var(--muted)', opacity: 0.6 }}>-</span>
                      )}
                    </td>
                    <td className="py-2 pr-4">{p.system_count}</td>
                    <td className="py-2 pr-4">
                      {p.is_active ? (
                        <span className="pill pill-emerald">Active</span>
                      ) : (
                        <span className="pill pill-red">Inactive</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-xs" style={{ color: 'var(--muted)' }}>
                      {p.last_login_at ? new Date(p.last_login_at).toLocaleDateString() : 'Never'}
                    </td>
                    {canManage && (
                      <td className="py-2">
                        <div className="flex gap-1 flex-wrap">
                          {/* Edit button - for partners and sub-admins */}
                          {(p.tier === 2 || p.tier === 3) && (isSuperAdmin || (isPartner && p.tier === 3)) && (
                            <button
                              onClick={() => openEditModal(p)}
                              className="haven-btn-ghost px-2 py-1 text-xs rounded"
                            >
                              Edit
                            </button>
                          )}
                          {/* Change Tier - super admin only, for users with passwords.
                              Only handles non-membership-derived tiers (super_admin,
                              member, read-only). Partner / sub-admin are managed via
                              Civilizations page → Add Member. */}
                          {isSuperAdmin && p.has_password && (
                            <button
                              onClick={() => {
                                setElevateProfile(p)
                                const allowed = [1, 4, 5]
                                const startTier = allowed.includes(p.tier) ? p.tier : 4
                                setElevateForm({ tier: startTier, partner_discord_tag: '', enabled_features: [], parent_profile_id: null, additional_discord_tags: [], can_approve_personal_uploads: false })
                              }}
                              className="pill pill-blue pill-clickable"
                              title="Change non-membership tier (Super Admin / Member / Read-Only). Partner / Sub-Admin are managed via Civilizations."
                            >
                              Change Tier
                            </button>
                          )}
                          {/* Demote - super admin only, for partners/sub-admins */}
                          {isSuperAdmin && p.tier >= 2 && p.tier <= 3 && (
                            <button
                              onClick={() => {
                                if (confirm(`Demote ${p.username} to Member?`)) {
                                  axios.put(`/api/admin/profiles/${p.id}/tier`, { tier: 4 })
                                    .then(() => fetchProfiles())
                                    .catch(err => alert(err.response?.data?.detail || 'Failed'))
                                }
                              }}
                              className="pill pill-amber pill-clickable"
                            >
                              Demote
                            </button>
                          )}
                          {/* Reset Password */}
                          {(isSuperAdmin || (isPartner && p.tier === 3)) && p.tier > 1 && (
                            <button
                              onClick={() => { setResetProfile(p); setResetPassword('') }}
                              className="pill pill-amber pill-clickable"
                            >
                              Reset PW
                            </button>
                          )}
                          {/* Activate/Deactivate */}
                          {(isSuperAdmin || (isPartner && p.tier === 3)) && p.tier > 1 && (
                            <button
                              onClick={() => toggleActive(p)}
                              className={`pill pill-clickable ${p.is_active ? 'pill-red' : 'pill-emerald'}`}
                            >
                              {p.is_active ? 'Deactivate' : 'Activate'}
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
                {profiles.length === 0 && (
                  <tr><td colSpan={7} className="py-8 text-center" style={{ color: 'var(--muted)' }}>No profiles found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex justify-center gap-2 mt-4">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="haven-btn-ghost px-3 py-1 text-sm rounded">Prev</button>
            <span className="text-sm py-1" style={{ color: 'var(--muted)' }}>Page {page} of {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="haven-btn-ghost px-3 py-1 text-sm rounded">Next</button>
          </div>
        )}
      </Card>

      {/* ========== EDIT MODAL ========== */}
      {editProfile && (
        <div className="haven-modal" onClick={() => setEditProfile(null)}>
          <div className="haven-modal-panel" onClick={e => e.stopPropagation()}>
            <div className="haven-modal-header">
              <span>Edit {editProfile.username}</span>
            </div>
            <div className="haven-modal-body">
              <div className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
                <span className={tierPill(editProfile.tier)}>
                  {TIER_LABELS[editProfile.tier]}
                </span>
                {editProfile.partner_discord_tag && (
                  <span className="ml-2" style={{ color: 'var(--app-primary)' }}>{editProfile.partner_discord_tag}</span>
                )}
                {editProfile.parent_info && (
                  <span className="ml-2">under {editProfile.parent_info.username} ({editProfile.parent_info.partner_discord_tag})</span>
                )}
              </div>

              <div className="space-y-4">
                {/* Display Name */}
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--muted)' }}>Display Name</label>
                  <input
                    value={editForm.display_name}
                    onChange={e => setEditForm({ ...editForm, display_name: e.target.value })}
                    className="haven-input w-full p-2"
                  />
                </div>

                {/* Feature permissions */}
                <div>
                  <label className="block text-sm mb-2" style={{ color: 'var(--muted)' }}>Permissions</label>
                  <div className="grid grid-cols-2 gap-2">
                    {(editProfile.tier === 2 ? PARTNER_FEATURES : SUB_ADMIN_FEATURES).map(f => (
                      <label key={f.key} className="flex items-center gap-2 text-sm cursor-pointer p-1 rounded hover:bg-white/5">
                        <input
                          type="checkbox"
                          checked={editForm.enabled_features.includes(f.key)}
                          onChange={() => toggleFeature(f.key)}
                          className="rounded"
                        />
                        <span>{f.label}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Sub-admin specific: additional discord tags */}
                {editProfile.tier === 3 && !editProfile.parent_profile_id && (
                  <div>
                    <label className="block text-sm mb-1" style={{ color: 'var(--muted)' }}>Additional Community Tags (Haven sub-admins)</label>
                    <p className="text-xs mb-2" style={{ color: 'var(--muted)' }}>Tags this sub-admin can see pending approvals for, in addition to Haven.</p>
                    <div className="flex flex-wrap gap-2">
                      {partners.map(p => p.partner_discord_tag && (
                        <label key={p.id} className="flex items-center gap-1 text-xs cursor-pointer px-2 py-1 rounded" style={{ background: 'rgba(255,255,255,0.05)' }}>
                          <input
                            type="checkbox"
                            checked={editForm.additional_discord_tags.includes(p.partner_discord_tag)}
                            onChange={() => {
                              const tags = editForm.additional_discord_tags
                              setEditForm({
                                ...editForm,
                                additional_discord_tags: tags.includes(p.partner_discord_tag)
                                  ? tags.filter(t => t !== p.partner_discord_tag)
                                  : [...tags, p.partner_discord_tag]
                              })
                            }}
                          />
                          <span style={{ color: 'var(--app-primary)' }}>{p.partner_discord_tag}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sub-admin specific: can_approve_personal_uploads */}
                {editProfile.tier === 3 && !editProfile.parent_profile_id && (
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editForm.can_approve_personal_uploads}
                      onChange={e => setEditForm({ ...editForm, can_approve_personal_uploads: e.target.checked })}
                    />
                    <span>Can approve personal uploads</span>
                  </label>
                )}

                {/* Stats */}
                {editProfile.stats && (
                  <div className="text-xs pt-2" style={{ color: 'var(--muted)', borderTop: '1px solid var(--border-soft)' }}>
                    {editProfile.stats.systems} systems, {editProfile.stats.discoveries} discoveries
                    {editProfile.created_at && <span className="ml-3">Member since {new Date(editProfile.created_at).toLocaleDateString()}</span>}
                  </div>
                )}
              </div>
            </div>
            <div className="haven-modal-footer">
              <button onClick={() => setEditProfile(null)} className="haven-btn-ghost px-3 py-1.5 rounded">Cancel</button>
              <button onClick={saveEdit} disabled={editSaving} className="haven-btn-primary px-3 py-1.5 rounded">
                {editSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========== ELEVATE MODAL ==========
          v1.55.0: civ-membership-derived tiers (Partner / Sub-Admin) were
          removed from this flow. The backend `_recompute_profile_tier` in
          routes/civilizations.py auto-syncs user_profiles.tier from the
          civilization_members table on every add/update/remove, so any
          tier=2/tier=3 set here without a matching membership row would be
          silently wiped on the next civ change. To make someone a Partner
          or Sub-Admin, use Civilizations page → Add Member with the
          appropriate role. This modal now only handles non-civ tier
          changes: promote to Super Admin, or demote to Member / Read-Only. */}
      {elevateProfile && (
        <div className="haven-modal" onClick={() => setElevateProfile(null)}>
          <div className="haven-modal-panel" onClick={e => e.stopPropagation()}>
            <div className="haven-modal-header">
              <span>Change Tier — {elevateProfile.username}</span>
            </div>
            <div className="haven-modal-body">
              <div className="space-y-4">
                <div className="haven-card p-3 text-xs" style={{ color: 'var(--app-primary)', borderColor: 'var(--app-primary)' }}>
                  <strong className="block mb-1">Partner / Sub-Admin tiers are now membership-derived.</strong>
                  To make this user a leader or moderator of a community, open the{' '}
                  <a href="/haven-ui/admin/civilizations" className="underline">Civilizations</a> page,
                  pick a civ, and add them with role <code>leader</code>, <code>co_leader</code>, or <code>sub_admin</code>.
                  Their tier syncs automatically. Use this modal only for promoting to Super Admin or
                  demoting to Member / Read-Only.
                </div>

                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--muted)' }}>New Tier</label>
                  <select
                    value={elevateForm.tier}
                    onChange={e => setElevateForm({ ...elevateForm, tier: parseInt(e.target.value), enabled_features: [], partner_discord_tag: '', parent_profile_id: null })}
                    className="haven-input w-full p-2"
                  >
                    <option value={1}>Super Admin</option>
                    <option value={4}>Member</option>
                    <option value={5}>Read-Only Member</option>
                  </select>
                </div>

                {elevateForm.tier === 1 && (
                  <div className="haven-card p-3 text-xs" style={{ color: 'var(--app-accent-amber)', borderColor: 'var(--app-accent-amber)' }}>
                    ⚠ Super Admin has unrestricted access to all communities, settings, and destructive operations. Confirm intent.
                  </div>
                )}

                {(elevateForm.tier === 4 || elevateForm.tier === 5) && (
                  <div className="haven-card p-3 text-xs" style={{ color: 'var(--muted)' }}>
                    If this user is currently a leader of any civilization, demoting their tier here
                    will be overridden the next time their civ membership changes. To fully step them
                    down, remove their <code>civilization_members</code> row first.
                  </div>
                )}
              </div>
            </div>
            <div className="haven-modal-footer">
              <button onClick={() => setElevateProfile(null)} className="haven-btn-ghost px-3 py-1.5 rounded">Cancel</button>
              <button
                onClick={handleElevate}
                disabled={elevating}
                className="haven-btn-primary px-3 py-1.5 rounded"
              >
                {elevating ? 'Saving...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========== RESET PASSWORD MODAL ========== */}
      {resetProfile && (
        <div className="haven-modal" onClick={() => setResetProfile(null)}>
          <div className="haven-modal-panel haven-modal-panel-narrow" onClick={e => e.stopPropagation()}>
            <div className="haven-modal-header">
              <span>Reset Password for {resetProfile.username}</span>
            </div>
            <div className="haven-modal-body">
              <div className="space-y-3">
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--muted)' }}>New Password</label>
                  <input
                    type="password"
                    value={resetPassword}
                    onChange={e => setResetPassword(e.target.value)}
                    placeholder="At least 4 characters"
                    className="haven-input w-full p-2"
                  />
                </div>
              </div>
            </div>
            <div className="haven-modal-footer">
              <button onClick={() => setResetProfile(null)} className="haven-btn-ghost px-3 py-1.5 rounded">Cancel</button>
              <button onClick={handleResetPassword} disabled={resetting || resetPassword.length < 4} className="haven-btn-primary px-3 py-1.5 rounded">
                {resetting ? 'Resetting...' : 'Reset Password'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
