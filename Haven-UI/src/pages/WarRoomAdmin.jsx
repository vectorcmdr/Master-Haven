import React, { useState, useEffect, useContext } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { AuthContext } from '../utils/AuthContext'

/**
 * War Room Administration
 * Route: /war-room/admin
 * Auth: Super admin only
 *
 * Admin panel for the War Room system. Manages civilization enrollment,
 * war correspondents, reporting organizations and their members, home
 * region assignments, conflict resolution, and news article moderation.
 *
 * Key APIs:
 *   GET/POST /api/warroom/enrollment
 *   GET/POST /api/warroom/correspondents
 *   GET/POST /api/warroom/reporting-orgs
 *   GET/POST /api/warroom/reporting-orgs/:id/members
 *   GET      /api/warroom/conflicts?status=resolved
 *   GET      /api/warroom/news?limit=50
 *   GET      /api/partners  (for enrollment dropdown)
 */
export default function WarRoomAdmin() {
  const auth = useContext(AuthContext)
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [enrolledCivs, setEnrolledCivs] = useState([])
  const [allPartners, setAllPartners] = useState([])
  const [correspondents, setCorrespondents] = useState([])
  const [selectedPartner, setSelectedPartner] = useState('')
  const [newCorrespondent, setNewCorrespondent] = useState({ username: '', password: '', display_name: '' })
  const [message, setMessage] = useState(null)
  const [editingHomeRegion, setEditingHomeRegion] = useState(null)
  const [homeRegionForm, setHomeRegionForm] = useState({ region_x: '', region_y: '', region_z: '', region_name: '', galaxy: 'Euclid' })
  const [regionSearchQuery, setRegionSearchQuery] = useState('')
  const [regionSearchResults, setRegionSearchResults] = useState([])
  const [searchingRegions, setSearchingRegions] = useState(false)

  // Reporting Organizations state
  const [reportingOrgs, setReportingOrgs] = useState([])
  const [newOrg, setNewOrg] = useState({ name: '', description: '', discord_server_name: '' })
  const [selectedOrg, setSelectedOrg] = useState(null)
  const [orgMembers, setOrgMembers] = useState([])
  const [newOrgMember, setNewOrgMember] = useState({ username: '', password: '', display_name: '' })
  const [conflictHistory, setConflictHistory] = useState([])

  // News management state
  const [newsArticles, setNewsArticles] = useState([])

  // Redirect if not super admin
  useEffect(() => {
    if (!auth.loading && !auth.isSuperAdmin) {
      navigate('/war-room')
    }
  }, [auth.loading, auth.isSuperAdmin, navigate])

  const fetchData = async () => {
    try {
      const [enrollmentRes, partnersRes, correspondentsRes, orgsRes, historyRes, newsRes] = await Promise.all([
        axios.get('/api/warroom/enrollment'),
        axios.get('/api/partners'),
        axios.get('/api/warroom/correspondents'),
        axios.get('/api/warroom/reporting-orgs'),
        axios.get('/api/warroom/conflicts?status=resolved'),
        axios.get('/api/warroom/news?limit=50')
      ])

      setEnrolledCivs(enrollmentRes.data)
      setAllPartners(partnersRes.data.partners || [])
      setCorrespondents(correspondentsRes.data)
      setReportingOrgs(orgsRes.data)
      setConflictHistory(historyRes.data)
      setNewsArticles(newsRes.data)
    } catch (err) {
      console.error('Failed to fetch admin data:', err)
    } finally {
      setLoading(false)
    }
  }

  // Fetch org members when selecting an org
  const fetchOrgMembers = async (orgId) => {
    try {
      const res = await axios.get(`/api/warroom/reporting-orgs/${orgId}/members`)
      setOrgMembers(res.data)
    } catch (err) {
      console.error('Failed to fetch org members:', err)
      setOrgMembers([])
    }
  }

  // Create reporting organization
  const createReportingOrg = async () => {
    if (!newOrg.name) {
      setMessage({ type: 'error', text: 'Organization name is required' })
      return
    }
    try {
      await axios.post('/api/warroom/reporting-orgs', newOrg)
      setMessage({ type: 'success', text: 'News organization created!' })
      setNewOrg({ name: '', description: '', discord_server_name: '' })
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to create organization' })
    }
  }

  // Add member to reporting org
  const addOrgMember = async () => {
    if (!selectedOrg || !newOrgMember.username || !newOrgMember.password) {
      setMessage({ type: 'error', text: 'Username and password required' })
      return
    }
    try {
      await axios.post(`/api/warroom/reporting-orgs/${selectedOrg.id}/members`, newOrgMember)
      setMessage({ type: 'success', text: 'Member added!' })
      setNewOrgMember({ username: '', password: '', display_name: '' })
      fetchOrgMembers(selectedOrg.id)
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to add member' })
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const enrollPartner = async () => {
    if (!selectedPartner) return

    try {
      const res = await axios.post('/api/warroom/enrollment', { partner_id: parseInt(selectedPartner) })
      const systemsClaimed = res.data.systems_claimed || 0
      setMessage({
        type: 'success',
        text: `Partner enrolled successfully! Auto-claimed ${systemsClaimed} systems based on discord_tag.`
      })
      setSelectedPartner('')
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to enroll partner' })
    }
  }

  const syncTerritory = async (partnerId) => {
    try {
      const res = await axios.post(`/api/warroom/enrollment/${partnerId}/sync-territory`)
      setMessage({
        type: 'success',
        text: `Synced ${res.data.systems_claimed} new systems for ${res.data.display_name}`
      })
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to sync territory' })
    }
  }

  const syncAllTerritory = async () => {
    try {
      const res = await axios.post('/api/warroom/sync-all-territory')
      const results = res.data.civs_updated || []
      const totalSystems = res.data.total_systems_claimed || 0
      if (totalSystems === 0) {
        setMessage({ type: 'success', text: 'All civilizations are already synced - no new systems to claim.' })
      } else {
        setMessage({
          type: 'success',
          text: `Synced ${totalSystems} total systems across ${results.length} civilizations.`
        })
      }
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to sync all territory' })
    }
  }

  const unenrollPartner = async (partnerId) => {
    if (!confirm('Are you sure you want to unenroll this civilization from the War Room?')) return

    try {
      await axios.delete(`/api/warroom/enrollment/${partnerId}`)
      setMessage({ type: 'success', text: 'Partner unenrolled successfully' })
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to unenroll partner' })
    }
  }

  const createCorrespondent = async () => {
    if (!newCorrespondent.username || !newCorrespondent.password) {
      setMessage({ type: 'error', text: 'Username and password required' })
      return
    }

    try {
      await axios.post('/api/warroom/correspondents', newCorrespondent)
      setMessage({ type: 'success', text: 'Correspondent created successfully!' })
      setNewCorrespondent({ username: '', password: '', display_name: '' })
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to create correspondent' })
    }
  }

  const recalculateStats = async () => {
    try {
      await axios.post('/api/warroom/statistics/recalculate')
      setMessage({ type: 'success', text: 'Statistics recalculated! Note: Stats require resolved conflicts to populate.' })
    } catch (err) {
      console.error('Recalculate stats error:', err)
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to recalculate statistics' })
    }
  }

  const deleteNewsArticle = async (newsId, headline) => {
    if (!confirm(`Are you sure you want to delete "${headline}"?`)) return

    try {
      await axios.delete(`/api/warroom/news/${newsId}`)
      setMessage({ type: 'success', text: 'News article deleted successfully' })
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to delete news article' })
    }
  }

  const openHomeRegionEditor = (civ) => {
    setEditingHomeRegion(civ)
    setHomeRegionForm({
      region_x: civ.home_region_x ?? '',
      region_y: civ.home_region_y ?? '',
      region_z: civ.home_region_z ?? '',
      region_name: civ.home_region_name ?? '',
      galaxy: civ.home_galaxy ?? 'Euclid'
    })
    setRegionSearchQuery('')
    setRegionSearchResults([])
  }

  // Search for regions when editing home region
  useEffect(() => {
    if (!editingHomeRegion || regionSearchQuery.length < 2) {
      setRegionSearchResults([])
      return
    }

    const timer = setTimeout(async () => {
      setSearchingRegions(true)
      try {
        // Search for systems by the partner's discord_tag
        const res = await axios.get(`/api/warroom/territory/search?q=${encodeURIComponent(regionSearchQuery)}&discord_tag=${encodeURIComponent(editingHomeRegion.discord_tag)}&limit=20`)
        setRegionSearchResults(res.data)
      } catch (err) {
        console.error('Region search failed:', err)
      } finally {
        setSearchingRegions(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [regionSearchQuery, editingHomeRegion])

  const selectRegionFromSearch = (system) => {
    setHomeRegionForm({
      region_x: system.region_x ?? '',
      region_y: system.region_y ?? '',
      region_z: system.region_z ?? '',
      region_name: system.region_name || '',
      galaxy: system.galaxy || 'Euclid'
    })
    setRegionSearchQuery('')
    setRegionSearchResults([])
  }

  const saveHomeRegion = async () => {
    if (!editingHomeRegion) return

    try {
      await axios.put(`/api/warroom/enrollment/${editingHomeRegion.partner_id}/home-region`, {
        region_x: homeRegionForm.region_x ? parseInt(homeRegionForm.region_x) : null,
        region_y: homeRegionForm.region_y ? parseInt(homeRegionForm.region_y) : null,
        region_z: homeRegionForm.region_z ? parseInt(homeRegionForm.region_z) : null,
        region_name: homeRegionForm.region_name || null,
        galaxy: homeRegionForm.galaxy
      })
      setMessage({ type: 'success', text: 'Home region updated!' })
      setEditingHomeRegion(null)
      fetchData()
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to update home region' })
    }
  }

  // Get partners not yet enrolled
  const enrolledIds = enrolledCivs.map(c => c.partner_id)
  const availablePartners = allPartners.filter(p => !enrolledIds.includes(p.id))

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--war-bg)' }}>
        <div className="text-xl animate-pulse" style={{ color: 'var(--war-accent)' }}>Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen -m-6" style={{ backgroundColor: 'var(--war-bg)', color: 'var(--war-text)' }}>
      {/* Header */}
      <div
        className="px-6 py-4 border-b"
        style={{ background: 'var(--war-card)', borderColor: 'var(--war-border-strong)' }}
      >
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold tracking-wider" style={{ color: 'var(--war-accent)' }}>WAR ROOM ADMIN</h1>
          <button
            onClick={() => navigate('/war-room')}
            className="war-btn-ghost px-4 py-2 rounded text-sm"
          >
            Back to War Room
          </button>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div className={`mx-6 mt-4 p-3 rounded war-pill ${message.type === 'success' ? 'war-pill-success' : 'war-pill-red'}`}>
          {message.text}
          <button onClick={() => setMessage(null)} className="ml-4 text-xs opacity-60 hover:opacity-100">Dismiss</button>
        </div>
      )}

      <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Enrolled Civilizations */}
        <div className="war-card">
          <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--war-border)' }}>
            <h2 className="text-lg font-bold" style={{ color: 'var(--war-accent)' }}>Enrolled Civilizations ({enrolledCivs.length})</h2>
          </div>
          <div className="p-4">
            {enrolledCivs.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--war-text-dim)' }}>No civilizations enrolled yet.</p>
            ) : (
              <div className="space-y-2">
                {enrolledCivs.map(civ => (
                  <div key={civ.partner_id} className="war-card p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-4 h-4 rounded-full"
                          style={{ backgroundColor: civ.region_color }}
                        />
                        <div>
                          <div className="font-medium">{civ.display_name}</div>
                          <div className="text-xs" style={{ color: 'var(--war-text-dim)' }}>{civ.discord_tag}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => syncTerritory(civ.partner_id)}
                          className="war-btn-success px-2 py-1 rounded text-xs"
                          title="Sync new systems from discord_tag"
                        >
                          Sync
                        </button>
                        <button
                          onClick={() => unenrollPartner(civ.partner_id)}
                          className="war-btn-danger px-2 py-1 rounded text-xs"
                        >
                          Unenroll
                        </button>
                      </div>
                    </div>
                    {/* Home Region */}
                    <div className="mt-2 pt-2 border-t" style={{ borderColor: 'var(--war-border)' }}>
                      {civ.home_region_x !== null ? (
                        <div className="flex items-center justify-between">
                          <div className="text-xs" style={{ color: 'var(--war-text-dim)' }}>
                            Home: <span style={{ color: 'var(--war-text)' }}>{civ.home_region_name || `(${civ.home_region_x}, ${civ.home_region_y}, ${civ.home_region_z})`}</span>
                            <span className="ml-1">- {civ.home_galaxy}</span>
                          </div>
                          <button
                            onClick={() => openHomeRegionEditor(civ)}
                            className="text-xs hover:opacity-80"
                            style={{ color: 'var(--war-accent)' }}
                          >
                            Edit
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => openHomeRegionEditor(civ)}
                          className="text-xs hover:opacity-80"
                          style={{ color: 'var(--war-accent)' }}
                        >
                          + Set Home Region
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Enroll new partner */}
            <div className="mt-4 pt-4 border-t" style={{ borderColor: 'var(--war-border)' }}>
              <label className="block text-sm mb-2" style={{ color: 'var(--war-text-dim)' }}>Enroll New Civilization</label>
              <div className="flex gap-2">
                <select
                  value={selectedPartner}
                  onChange={(e) => setSelectedPartner(e.target.value)}
                  className="war-input flex-1 rounded px-3 py-2 text-sm"
                >
                  <option value="">Select a partner...</option>
                  {availablePartners.map(p => (
                    <option key={p.id} value={p.id}>{p.display_name} ({p.discord_tag})</option>
                  ))}
                </select>
                <button
                  onClick={enrollPartner}
                  disabled={!selectedPartner}
                  className="war-btn-success px-4 py-2 rounded text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Enroll
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* War Correspondents */}
        <div className="war-card">
          <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--war-border)' }}>
            <h2 className="text-lg font-bold" style={{ color: 'var(--war-accent)' }}>War Correspondents ({correspondents.length})</h2>
          </div>
          <div className="p-4">
            {correspondents.length > 0 && (
              <div className="space-y-2 mb-4">
                {correspondents.map(c => (
                  <div key={c.id} className="war-card flex items-center justify-between p-3">
                    <div>
                      <div className="font-medium">{c.display_name || c.username}</div>
                      <div className="text-xs" style={{ color: 'var(--war-text-dim)' }}>@{c.username}</div>
                    </div>
                    <span className={`war-pill ${c.is_active ? 'war-pill-success' : 'war-pill-muted'}`}>
                      {c.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Create new correspondent */}
            <div className="space-y-3 pt-4 border-t" style={{ borderColor: 'var(--war-border)' }}>
              <label className="block text-sm" style={{ color: 'var(--war-text-dim)' }}>Create New Correspondent</label>
              <input
                type="text"
                placeholder="Username"
                value={newCorrespondent.username}
                onChange={(e) => setNewCorrespondent(prev => ({ ...prev, username: e.target.value }))}
                className="war-input w-full rounded px-3 py-2 text-sm"
              />
              <input
                type="password"
                placeholder="Password"
                value={newCorrespondent.password}
                onChange={(e) => setNewCorrespondent(prev => ({ ...prev, password: e.target.value }))}
                className="war-input w-full rounded px-3 py-2 text-sm"
              />
              <input
                type="text"
                placeholder="Display Name (optional)"
                value={newCorrespondent.display_name}
                onChange={(e) => setNewCorrespondent(prev => ({ ...prev, display_name: e.target.value }))}
                className="war-input w-full rounded px-3 py-2 text-sm"
              />
              <button
                onClick={createCorrespondent}
                className="war-btn-primary w-full py-2 rounded text-sm font-bold"
              >
                Create Correspondent
              </button>
            </div>
          </div>
        </div>

        {/* Reporting Organizations — yellow accent retained as semantic "news" channel */}
        <div className="war-card" style={{ borderColor: 'rgba(234, 179, 8, 0.3)' }}>
          <div className="px-4 py-3 border-b" style={{ borderColor: 'rgba(234, 179, 8, 0.3)' }}>
            <h2 className="text-lg font-bold text-yellow-400">News Organizations ({reportingOrgs.length})</h2>
          </div>
          <div className="p-4">
            {reportingOrgs.length > 0 && (
              <div className="space-y-2 mb-4">
                {reportingOrgs.map(org => (
                  <div
                    key={org.id}
                    onClick={() => {
                      setSelectedOrg(org)
                      fetchOrgMembers(org.id)
                    }}
                    className="war-card war-card-hover p-3 cursor-pointer"
                    style={
                      selectedOrg?.id === org.id
                        ? { borderColor: 'rgba(234, 179, 8, 0.5)', background: 'rgba(234, 179, 8, 0.15)' }
                        : undefined
                    }
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium" style={{ color: 'var(--war-text)' }}>{org.name}</div>
                        {org.discord_server_name && (
                          <div className="text-xs" style={{ color: 'var(--war-text-dim)' }}>{org.discord_server_name}</div>
                        )}
                      </div>
                      <span className="text-xs" style={{ color: 'var(--war-text-dim)' }}>{org.member_count} members</span>
                    </div>
                    {org.description && (
                      <p className="text-xs mt-1" style={{ color: 'var(--war-text-dim)' }}>{org.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Selected Org Members */}
            {selectedOrg && (
              <div className="war-card p-3 mb-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-bold text-yellow-400">{selectedOrg.name} Members</h4>
                  <button
                    onClick={() => setSelectedOrg(null)}
                    className="text-xs hover:opacity-80"
                    style={{ color: 'var(--war-text-dim)' }}
                  >
                    Close
                  </button>
                </div>
                {orgMembers.length > 0 ? (
                  <div className="space-y-1 mb-3">
                    {orgMembers.map(m => (
                      <div key={m.id} className="flex items-center justify-between text-sm">
                        <span style={{ color: 'var(--war-text)' }}>{m.display_name || m.username}</span>
                        <span className={`war-pill ${m.is_active ? 'war-pill-success' : 'war-pill-muted'}`}>
                          {m.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs mb-3" style={{ color: 'var(--war-text-dim)' }}>No members yet</p>
                )}
                <div className="space-y-2 border-t pt-3" style={{ borderColor: 'var(--war-border)' }}>
                  <input
                    type="text"
                    placeholder="Username"
                    value={newOrgMember.username}
                    onChange={(e) => setNewOrgMember(prev => ({ ...prev, username: e.target.value }))}
                    className="war-input w-full rounded px-2 py-1 text-xs"
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={newOrgMember.password}
                    onChange={(e) => setNewOrgMember(prev => ({ ...prev, password: e.target.value }))}
                    className="war-input w-full rounded px-2 py-1 text-xs"
                  />
                  <input
                    type="text"
                    placeholder="Display Name (optional)"
                    value={newOrgMember.display_name}
                    onChange={(e) => setNewOrgMember(prev => ({ ...prev, display_name: e.target.value }))}
                    className="war-input w-full rounded px-2 py-1 text-xs"
                  />
                  <button
                    onClick={addOrgMember}
                    className="w-full py-1.5 bg-yellow-600 hover:bg-yellow-500 rounded text-xs font-bold"
                  >
                    Add Member
                  </button>
                </div>
              </div>
            )}

            {/* Create new org */}
            <div className="space-y-2 pt-3 border-t" style={{ borderColor: 'var(--war-border)' }}>
              <label className="block text-sm" style={{ color: 'var(--war-text-dim)' }}>Create News Organization</label>
              <input
                type="text"
                placeholder="Organization Name"
                value={newOrg.name}
                onChange={(e) => setNewOrg(prev => ({ ...prev, name: e.target.value }))}
                className="war-input w-full rounded px-3 py-2 text-sm"
              />
              <input
                type="text"
                placeholder="Discord Server (optional)"
                value={newOrg.discord_server_name}
                onChange={(e) => setNewOrg(prev => ({ ...prev, discord_server_name: e.target.value }))}
                className="war-input w-full rounded px-3 py-2 text-sm"
              />
              <textarea
                placeholder="Description (optional)"
                value={newOrg.description}
                onChange={(e) => setNewOrg(prev => ({ ...prev, description: e.target.value }))}
                className="war-input w-full rounded px-3 py-2 text-sm"
                rows={2}
              />
              <button
                onClick={createReportingOrg}
                className="w-full py-2 bg-yellow-600 hover:bg-yellow-500 rounded text-sm font-bold"
              >
                Create Organization
              </button>
            </div>
          </div>
        </div>

        {/* Conflict History */}
        <div className="war-card">
          <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--war-border)' }}>
            <h2 className="text-lg font-bold" style={{ color: 'var(--war-text-dim)' }}>Conflict History ({conflictHistory.length})</h2>
          </div>
          <div className="p-4">
            {conflictHistory.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--war-text-dim)' }}>No resolved conflicts yet</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {conflictHistory.slice(0, 20).map(c => (
                  <div key={c.id} className="war-card p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-sm" style={{ color: 'var(--war-text)' }}>{c.target_system_name}</span>
                      <span className={`war-pill ${
                        c.resolution === 'attacker_victory' ? 'war-pill-red' :
                        c.resolution === 'defender_victory' ? 'war-pill-info' :
                        c.resolution === 'surrender' ? 'war-pill-warning' :
                        'war-pill-success'
                      }`}>
                        {c.resolution?.replace(/_/g, ' ') || 'Resolved'}
                      </span>
                    </div>
                    <div className="text-xs" style={{ color: 'var(--war-text-dim)' }}>
                      <span style={{ color: c.attacker?.color }}>{c.attacker?.display_name}</span>
                      {' vs '}
                      <span style={{ color: c.defender?.color }}>{c.defender?.display_name}</span>
                    </div>
                    <div className="text-xs mt-1" style={{ color: 'var(--war-text-dim)' }}>
                      {c.resolved_at ? new Date(c.resolved_at).toLocaleDateString() : 'Unknown date'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* News Management — yellow accent retained as semantic "news" channel */}
        <div className="war-card lg:col-span-2" style={{ borderColor: 'rgba(234, 179, 8, 0.3)' }}>
          <div className="px-4 py-3 border-b" style={{ borderColor: 'rgba(234, 179, 8, 0.3)' }}>
            <h2 className="text-lg font-bold text-yellow-400">News & Reports ({newsArticles.length})</h2>
          </div>
          <div className="p-4">
            {newsArticles.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--war-text-dim)' }}>No news articles yet</p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {newsArticles.map(article => (
                  <div key={article.id} className="war-card p-3 flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`war-pill ${
                          article.article_type === 'breaking' ? 'war-pill-red' :
                          article.article_type === 'editorial' ? 'war-pill-purple' :
                          article.article_type === 'report' ? 'war-pill-info' :
                          'war-pill-muted'
                        }`}>
                          {article.article_type || 'news'}
                        </span>
                        {article.is_pinned && (
                          <span className="text-xs text-yellow-400">📌 Pinned</span>
                        )}
                      </div>
                      <div className="font-medium text-sm truncate" style={{ color: 'var(--war-text)' }}>{article.headline}</div>
                      <div className="text-xs mt-1" style={{ color: 'var(--war-text-dim)' }}>
                        By {article.author_name || article.author_username}
                        {article.reporting_org_name && (
                          <span className="text-yellow-400"> • {article.reporting_org_name}</span>
                        )}
                        <span className="ml-2">
                          {new Date(article.published_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => deleteNewsArticle(article.id, article.headline)}
                      className="war-btn-danger px-2 py-1 rounded text-xs flex-shrink-0"
                      title="Delete this article"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Admin Actions */}
        <div className="war-card lg:col-span-2">
          <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--war-border)' }}>
            <h2 className="text-lg font-bold" style={{ color: 'var(--war-accent)' }}>Admin Actions</h2>
          </div>
          <div className="p-4 flex flex-wrap gap-4">
            <button
              onClick={syncAllTerritory}
              className="war-btn-success px-4 py-2 rounded text-sm font-bold"
              title="Sync all enrolled civs' territory from their discord_tags"
            >
              Sync All Territory
            </button>
            <button
              onClick={recalculateStats}
              className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 rounded text-sm font-bold"
            >
              Recalculate Statistics
            </button>
            <button
              onClick={() => navigate('/war-room')}
              className="war-btn-ghost px-4 py-2 rounded text-sm"
            >
              View War Room
            </button>
          </div>
        </div>
      </div>

      {/* Home Region Modal — cyan accent retained as semantic "HQ/identity" marker (matches war map HQ cyan ring) */}
      {editingHomeRegion && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="war-card p-6 w-full max-w-md" style={{ borderColor: 'rgba(34, 211, 209, 0.3)' }}>
            <h2 className="text-xl font-bold text-cyan-400 mb-4">
              Set Home Region: {editingHomeRegion.display_name}
            </h2>
            <div className="space-y-4">
              {/* Searchable Region Selector */}
              <div>
                <label className="block text-sm mb-2" style={{ color: 'var(--war-text-dim)' }}>Search Your Systems</label>
                <div className="relative">
                  <input
                    type="text"
                    value={regionSearchQuery}
                    onChange={(e) => setRegionSearchQuery(e.target.value)}
                    placeholder={`Search systems with ${editingHomeRegion.discord_tag} tag...`}
                    className="war-input w-full rounded px-3 py-2 text-sm"
                  />
                  {searchingRegions && (
                    <span className="absolute right-3 top-2 text-sm" style={{ color: 'var(--war-text-dim)' }}>...</span>
                  )}
                  {regionSearchResults.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 war-card shadow-lg max-h-48 overflow-y-auto">
                      {regionSearchResults.map(s => (
                        <button
                          key={s.id}
                          onClick={() => selectRegionFromSearch(s)}
                          className="w-full text-left px-3 py-2 hover:bg-white/5 text-sm border-b last:border-b-0"
                          style={{ borderColor: 'var(--war-border)' }}
                        >
                          <div className="font-medium" style={{ color: 'var(--war-text)' }}>{s.name}</div>
                          <div className="text-xs" style={{ color: 'var(--war-text-dim)' }}>
                            {s.region_name || `(${s.region_x}, ${s.region_y}, ${s.region_z})`} - {s.galaxy}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <p className="text-xs mt-1" style={{ color: 'var(--war-text-dim)' }}>Search for a system in {editingHomeRegion.discord_tag}'s territory</p>
              </div>

              {/* Selected Region Display */}
              {homeRegionForm.region_x !== '' && (
                <div className="war-card p-3" style={{ borderColor: 'rgba(34, 211, 209, 0.3)' }}>
                  <div className="text-sm mb-1" style={{ color: 'var(--war-text-dim)' }}>Selected Region:</div>
                  <div className="font-medium" style={{ color: 'var(--war-text)' }}>
                    {homeRegionForm.region_name || 'Unnamed Region'}
                  </div>
                  <div className="text-xs mt-1" style={{ color: 'var(--war-text-dim)' }}>
                    Coordinates: ({homeRegionForm.region_x}, {homeRegionForm.region_y}, {homeRegionForm.region_z}) • {homeRegionForm.galaxy}
                  </div>
                </div>
              )}

              {!homeRegionForm.region_x && homeRegionForm.region_x !== 0 && (
                <div className="text-sm text-yellow-400 text-center py-2">
                  Search and select a system to set as home region
                </div>
              )}

              <p className="text-xs" style={{ color: 'var(--war-text-dim)' }}>
                The home region (HQ) will be displayed on the war map and is protected from peace treaty demands.
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={saveHomeRegion}
                  disabled={homeRegionForm.region_x === '' && homeRegionForm.region_x !== 0}
                  className="flex-1 py-2 bg-cyan-600 hover:bg-cyan-500 rounded font-bold disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Save Home Region
                </button>
                <button
                  onClick={() => setEditingHomeRegion(null)}
                  className="war-btn-ghost px-4 py-2 rounded"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
