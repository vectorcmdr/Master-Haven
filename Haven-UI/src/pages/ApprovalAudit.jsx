import React, { useEffect, useState, useContext } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import { AuthContext } from '../utils/AuthContext'
import DateRangePicker from '../components/DateRangePicker'
import { format } from 'date-fns'

/**
 * Approval Audit Log — Route: /admin/audit
 * Auth: Super admin only; redirects to /systems otherwise.
 *
 * Paginated, filterable log of all approval/rejection actions.
 * Supports CSV and JSON export of filtered results.
 *
 * API endpoints:
 *   GET /api/approval_audit         — paginated audit entries with filters
 *   GET /api/approval_audit/export  — download filtered results as CSV or JSON
 *   GET /api/discord_tags           — community list for filter dropdown
 */

// Map action verb -> outcome pill (per 2.0 design conventions).
// Constructive approve/activate -> emerald; reject/revoke -> red;
// modify -> blue; super-admin special (reissue/force/suspend) -> amber.
function pillForAction(action) {
  if (!action) return 'pill-muted'
  const a = String(action).toLowerCase()
  if (
    a.startsWith('approve') ||
    a.startsWith('batch_approve') ||
    a === 'approved' ||
    a === 'activated' ||
    a === 'direct_add'
  ) return 'pill-emerald'
  if (
    a.startsWith('reject') ||
    a.startsWith('batch_reject') ||
    a === 'rejected' ||
    a === 'deactivated' ||
    a === 'revoke' ||
    a === 'revoked' ||
    a === 'delete' ||
    a === 'deleted' ||
    a === 'remove' ||
    a === 'removed'
  ) return 'pill-red'
  if (
    a.startsWith('edit') ||
    a === 'direct_edit' ||
    a === 'permission_change' ||
    a === 'tier_change' ||
    a === 'update' ||
    a === 'updated'
  ) return 'pill-blue'
  if (
    a === 'reissue_api_key' ||
    a === 'force_approve' ||
    a === 'override' ||
    a === 'suspend' ||
    a === 'suspended' ||
    a === 'password_reset'
  ) return 'pill-amber'
  return 'pill-muted'
}

export default function ApprovalAudit() {
  const navigate = useNavigate()
  const auth = useContext(AuthContext)
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const limit = 50

  // Filters
  const [filterApprover, setFilterApprover] = useState('')
  const [filterSubmitter, setFilterSubmitter] = useState('')
  const [filterDiscordTag, setFilterDiscordTag] = useState('')
  const [filterAction, setFilterAction] = useState('')
  const [filterSubmissionType, setFilterSubmissionType] = useState('')
  const [searchNotes, setSearchNotes] = useState('')
  const [filterSource, setFilterSource] = useState('')
  const [dateRange, setDateRange] = useState({ startDate: null, endDate: null })
  const [discordTags, setDiscordTags] = useState([])
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    if (!auth.isSuperAdmin) {
      alert('Super admin access required')
      navigate('/systems')
      return
    }
    loadDiscordTags()
    loadAuditLog()
  }, [auth.isSuperAdmin, navigate])

  useEffect(() => {
    loadAuditLog()
  }, [page, filterApprover, filterSubmitter, filterDiscordTag, filterAction, filterSubmissionType, searchNotes, filterSource, dateRange])

  async function loadDiscordTags() {
    try {
      const response = await axios.get('/api/discord_tags')
      setDiscordTags(response.data.tags || [])
    } catch (err) {
      console.error('Failed to load discord tags:', err)
    }
  }

  async function loadAuditLog() {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      params.append('limit', limit)
      params.append('offset', page * limit)
      if (filterApprover) params.append('approver', filterApprover)
      if (filterSubmitter) params.append('submitter', filterSubmitter)
      if (filterDiscordTag) params.append('discord_tag', filterDiscordTag)
      if (filterAction) params.append('action', filterAction)
      if (filterSubmissionType) params.append('submission_type', filterSubmissionType)
      if (searchNotes) params.append('search', searchNotes)
      if (filterSource) params.append('source', filterSource)
      if (dateRange.startDate) params.append('start_date', format(dateRange.startDate, 'yyyy-MM-dd'))
      if (dateRange.endDate) params.append('end_date', format(dateRange.endDate, 'yyyy-MM-dd'))

      const response = await axios.get(`/api/approval_audit?${params.toString()}`)
      setEntries(response.data.entries || [])
      setTotal(response.data.total || 0)
    } catch (err) {
      alert('Failed to load audit log: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  async function handleExport(exportFormat) {
    setExporting(true)
    try {
      const params = new URLSearchParams()
      params.append('format', exportFormat)
      if (filterApprover) params.append('approver', filterApprover)
      if (filterSubmitter) params.append('submitter', filterSubmitter)
      if (filterDiscordTag) params.append('discord_tag', filterDiscordTag)
      if (filterAction) params.append('action', filterAction)
      if (dateRange.startDate) params.append('start_date', format(dateRange.startDate, 'yyyy-MM-dd'))
      if (dateRange.endDate) params.append('end_date', format(dateRange.endDate, 'yyyy-MM-dd'))

      const response = await axios.get(`/api/approval_audit/export?${params.toString()}`, {
        responseType: exportFormat === 'csv' ? 'blob' : 'json'
      })

      if (exportFormat === 'csv') {
        const blob = new Blob([response.data], { type: 'text/csv' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `approval_audit_${format(new Date(), 'yyyy-MM-dd')}.csv`
        a.click()
        window.URL.revokeObjectURL(url)
      } else {
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `approval_audit_${format(new Date(), 'yyyy-MM-dd')}.json`
        a.click()
        window.URL.revokeObjectURL(url)
      }
    } catch (err) {
      alert('Failed to export: ' + (err.response?.data?.detail || err.message))
    } finally {
      setExporting(false)
    }
  }

  function clearFilters() {
    setFilterApprover('')
    setFilterSubmitter('')
    setFilterDiscordTag('')
    setFilterAction('')
    setFilterSubmissionType('')
    setSearchNotes('')
    setFilterSource('')
    setDateRange({ startDate: null, endDate: null })
    setPage(0)
  }

  function getActionBadge(action) {
    const labels = {
      approved: 'APPROVED',
      rejected: 'REJECTED',
      direct_edit: 'EDITED',
      direct_add: 'ADDED',
      edit_pending: 'EDIT PENDING',
      tier_change: 'TIER CHANGE',
      permission_change: 'PERMS CHANGED',
      activated: 'ACTIVATED',
      deactivated: 'DEACTIVATED',
      password_reset: 'PW RESET',
      reissue_api_key: 'KEY REISSUED',
      force_approve: 'FORCE APPROVED',
      override: 'OVERRIDE',
      suspend: 'SUSPENDED',
    }
    return (
      <span className={`pill ${pillForAction(action)}`}>
        {labels[action] || String(action).toUpperCase()}
      </span>
    )
  }

  function getSourceBadge(source) {
    if (!source) return null
    if (source === 'haven_extractor') return <span className="pill pill-purple ml-1">Extractor</span>
    if (source === 'keeper_bot') return <span className="pill pill-blue ml-1">Keeper</span>
    if (source === 'companion_app') return <span className="pill pill-teal ml-1">Companion</span>
    if (source === 'manual') return <span className="pill pill-muted ml-1">Manual</span>
    return null
  }

  function getApproverTypeBadge(type) {
    // Tier badge palette: super_admin=emerald, partner=blue, sub_admin=teal.
    const variants = {
      super_admin: 'pill-emerald',
      partner: 'pill-blue',
      sub_admin: 'pill-teal',
    }
    const labels = {
      super_admin: 'Super Admin',
      partner: 'Partner',
      sub_admin: 'Sub-Admin'
    }
    return (
      <span className={`pill ${variants[type] || 'pill-muted'}`}>
        {labels[type] || type}
      </span>
    )
  }

  const activeFilterCount = [
    filterApprover,
    filterSubmitter,
    filterDiscordTag,
    filterAction,
    filterSubmissionType,
    searchNotes,
    filterSource,
    dateRange.startDate
  ].filter(Boolean).length

  const totalPages = Math.ceil(total / limit)

  if (!auth.isSuperAdmin) {
    return null
  }

  return (
    <div className="p-4 md:p-6 w-full">
      <Card className="w-full">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold">Approval Audit Log</h2>
            <p className="text-sm mt-1 hidden sm:block" style={{ color: 'var(--muted)' }}>
              Track all approval and rejection actions across the system.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                className="haven-btn-ghost flex items-center gap-2 px-3 py-2 rounded text-sm font-medium transition-colors"
                onClick={() => document.getElementById('export-menu').classList.toggle('hidden')}
                disabled={exporting}
              >
                {exporting ? (
                  <span className="animate-spin">⏳</span>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                )}
                Export
              </button>
              <div id="export-menu" className="haven-card hidden absolute right-0 mt-1 w-32 z-10">
                <button
                  className="w-full px-4 py-2 text-left text-sm hover:bg-white/5"
                  onClick={() => {
                    document.getElementById('export-menu').classList.add('hidden')
                    handleExport('csv')
                  }}
                >
                  Export CSV
                </button>
                <button
                  className="w-full px-4 py-2 text-left text-sm hover:bg-white/5"
                  onClick={() => {
                    document.getElementById('export-menu').classList.add('hidden')
                    handleExport('json')
                  }}
                >
                  Export JSON
                </button>
              </div>
            </div>
            <Button className="haven-btn-ghost text-sm" onClick={() => navigate(-1)}>
              Back
            </Button>
          </div>
        </div>

        {/* Enhanced Filters */}
        <div className="haven-card mb-6 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>Filters</h3>
            {activeFilterCount > 0 && (
              <button
                className="text-xs flex items-center gap-1"
                style={{ color: 'var(--app-primary)' }}
                onClick={clearFilters}
              >
                Clear {activeFilterCount} filter{activeFilterCount > 1 ? 's' : ''}
                <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-4">
            {/* Date Range */}
            <div className="sm:col-span-2 md:col-span-1">
              <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Date Range</label>
              <DateRangePicker
                startDate={dateRange.startDate}
                endDate={dateRange.endDate}
                onChange={({ startDate, endDate }) => {
                  setDateRange({ startDate, endDate })
                  setPage(0)
                }}
              />
            </div>

            {/* Action */}
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Action</label>
              <select
                className="haven-input w-full p-2 text-sm"
                value={filterAction}
                onChange={(e) => {
                  setFilterAction(e.target.value)
                  setPage(0)
                }}
              >
                <option value="">All</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="direct_edit">Direct Edit</option>
                <option value="direct_add">Direct Add</option>
                <option value="edit_pending">Edit Pending</option>
                <option value="tier_change">Tier Change</option>
                <option value="permission_change">Permission Change</option>
                <option value="activated">Activated</option>
                <option value="deactivated">Deactivated</option>
                <option value="password_reset">Password Reset</option>
              </select>
            </div>

            {/* Submission Type */}
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Type</label>
              <select
                className="haven-input w-full p-2 text-sm"
                value={filterSubmissionType}
                onChange={(e) => {
                  setFilterSubmissionType(e.target.value)
                  setPage(0)
                }}
              >
                <option value="">All</option>
                <option value="system">System</option>
                <option value="discovery">Discovery</option>
                <option value="region">Region</option>
                <option value="profile">Profile</option>
              </select>
            </div>

            {/* Source */}
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Source</label>
              <select
                className="haven-input w-full p-2 text-sm"
                value={filterSource}
                onChange={(e) => {
                  setFilterSource(e.target.value)
                  setPage(0)
                }}
              >
                <option value="">All</option>
                <option value="manual">Manual</option>
                <option value="haven_extractor">Extractor</option>
                <option value="keeper_bot">Keeper Bot</option>
                {/* "Companion App" was folded into haven_extractor in v1.49.0;
                    migration 1.69.0 backfilled the existing rows. The
                    dropdown still listed it as if it were a current source,
                    which always returned zero rows. */}
              </select>
            </div>

            {/* Community */}
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Community</label>
              <select
                className="haven-input w-full p-2 text-sm"
                value={filterDiscordTag}
                onChange={(e) => {
                  setFilterDiscordTag(e.target.value)
                  setPage(0)
                }}
              >
                <option value="">All</option>
                {discordTags.map(t => (
                  <option key={t.tag} value={t.tag}>{t.name}</option>
                ))}
              </select>
            </div>

            {/* Approver */}
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Approver</label>
              <input
                type="text"
                className="haven-input w-full p-2 text-sm"
                placeholder="Username..."
                value={filterApprover}
                onChange={(e) => {
                  setFilterApprover(e.target.value)
                  setPage(0)
                }}
              />
            </div>

            {/* Submitter */}
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Submitter</label>
              <input
                type="text"
                className="haven-input w-full p-2 text-sm"
                placeholder="Username..."
                value={filterSubmitter}
                onChange={(e) => {
                  setFilterSubmitter(e.target.value)
                  setPage(0)
                }}
              />
            </div>

            {/* Search Notes */}
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Search</label>
              <input
                type="text"
                className="haven-input w-full p-2 text-sm"
                placeholder="Notes..."
                value={searchNotes}
                onChange={(e) => {
                  setSearchNotes(e.target.value)
                  setPage(0)
                }}
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: 'var(--app-primary)' }}></div>
          </div>
        ) : entries.length === 0 ? (
          <div className="haven-card italic p-4 text-center" style={{ color: 'var(--muted)' }}>
            No audit entries found matching your filters.
          </div>
        ) : (
          <>
            {/* Mobile Card Layout */}
            <div className="md:hidden space-y-3">
              {entries.map(entry => (
                <div key={entry.id} className="haven-card p-3">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="font-semibold">{entry.submission_name || 'Unknown'}</div>
                    {getActionBadge(entry.action)}
                  </div>
                  <div className="text-xs mb-2 flex items-center gap-1" style={{ color: 'var(--muted)' }}>
                    {entry.submission_type} {entry.submission_id === 0 ? '(Direct)' : `#${entry.submission_id}`}
                    {getSourceBadge(entry.source)}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>Approver</div>
                      <div>{entry.approver_username}</div>
                      <div className="mt-1">{getApproverTypeBadge(entry.approver_type)}</div>
                    </div>
                    <div>
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>Submitter</div>
                      <div>{entry.submitter_username || 'Unknown'}</div>
                    </div>
                    <div>
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>Community</div>
                      {entry.submission_discord_tag ? (
                        <span className="pill pill-teal">
                          {entry.submission_discord_tag}
                        </span>
                      ) : (
                        <span className="text-xs" style={{ color: 'var(--muted)' }}>Untagged</span>
                      )}
                    </div>
                    <div>
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>Date</div>
                      <div className="text-xs">{new Date(entry.timestamp).toLocaleDateString()}</div>
                    </div>
                  </div>
                  {entry.notes && (
                    <div className="mt-2 pt-2 hairline">
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>Notes</div>
                      <div className="text-xs line-clamp-2">{entry.notes}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Desktop Table Layout */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm table-fixed">
                <thead style={{ background: 'rgba(255,255,255,0.04)' }}>
                  <tr>
                    <th className="px-4 py-3 text-left w-[160px]">Timestamp</th>
                    <th className="px-4 py-3 text-left w-[100px]">Action</th>
                    <th className="px-4 py-3 text-left w-[200px]">Submission</th>
                    <th className="px-4 py-3 text-left w-[160px]">Approver</th>
                    <th className="px-4 py-3 text-left w-[140px]">Submitter</th>
                    <th className="px-4 py-3 text-left w-[120px]">Community</th>
                    <th className="px-4 py-3 text-left">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map(entry => (
                    <tr key={entry.id} className="hover:bg-white/5" style={{ borderBottom: '1px solid var(--border-soft)' }}>
                      <td className="px-4 py-3 whitespace-nowrap" style={{ color: 'var(--muted)' }}>
                        {new Date(entry.timestamp).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        {getActionBadge(entry.action)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold truncate" title={entry.submission_name || 'Unknown'}>
                          {entry.submission_name || 'Unknown'}
                        </div>
                        <div className="text-xs mt-1 flex items-center gap-1" style={{ color: 'var(--muted)' }}>
                          {entry.submission_type} {entry.submission_id === 0 ? '(Direct)' : `#${entry.submission_id}`}
                          {getSourceBadge(entry.source)}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold truncate" title={entry.approver_username}>
                          {entry.approver_username}
                        </div>
                        <div className="mt-1">{getApproverTypeBadge(entry.approver_type)}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="truncate" title={entry.submitter_username || 'Unknown'}>
                          {entry.submitter_username || 'Unknown'}
                        </div>
                        {entry.submitter_type && (
                          <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>{entry.submitter_type}</div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {entry.submission_discord_tag ? (
                          <span className="pill pill-teal">
                            {entry.submission_discord_tag}
                          </span>
                        ) : (
                          <span className="text-xs" style={{ color: 'var(--muted)' }}>Untagged</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {entry.notes ? (
                          <span className="block truncate" title={entry.notes}>
                            {entry.notes}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--muted)' }}>-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mt-6 pt-4 hairline">
              <p className="text-xs sm:text-sm text-center sm:text-left" style={{ color: 'var(--muted)' }}>
                {page * limit + 1}-{Math.min((page + 1) * limit, total)} of {total}
              </p>
              <div className="flex justify-center gap-2">
                <Button
                  className="haven-btn-ghost text-sm px-3 py-1"
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  Prev
                </Button>
                <span className="text-sm flex items-center px-2" style={{ color: 'var(--muted)' }}>
                  {page + 1}/{totalPages || 1}
                </span>
                <Button
                  className="haven-btn-ghost text-sm px-3 py-1"
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= totalPages - 1}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
