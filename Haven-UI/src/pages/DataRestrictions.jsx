import React, { useEffect, useState, useContext, useMemo } from 'react'
import { AuthContext } from '../utils/AuthContext'
import Card from '../components/Card'
import Button from '../components/Button'

/**
 * Data Restrictions — Route: /data-restrictions
 * Auth: Admin (partner or super admin) required.
 *
 * Manages per-system visibility rules that control what public viewers can see.
 * Supports single-system and bulk operations. Three restriction types:
 *   - Hide from public entirely (is_hidden_from_public toggle)
 *   - Hide specific fields (coordinates, glyphs, discoverer, etc.)
 *   - Map visibility (normal / point-only / hidden)
 *
 * API endpoints:
 *   GET    /api/partner/my_systems           — systems owned by this partner (or all for super admin)
 *   POST   /api/data_restrictions            — create/update restriction for one system
 *   DELETE /api/data_restrictions/:id        — remove restriction from one system
 *   POST   /api/data_restrictions/bulk       — apply restrictions to multiple systems
 *   POST   /api/data_restrictions/bulk_remove — remove restrictions from multiple systems
 */

// Restrictable field options with descriptions
const RESTRICTABLE_FIELDS = [
  { id: 'coordinates', label: 'Coordinates', description: 'X, Y, Z position and region coordinates' },
  { id: 'glyph_code', label: 'Portal Glyphs', description: 'Glyph code and portal address' },
  { id: 'discovered_by', label: 'Discoverer', description: 'Who discovered the system and when' },
  { id: 'base_location', label: 'Base Locations', description: 'Base coordinates on planets' },
  { id: 'description', label: 'Description', description: 'System description text' },
  { id: 'star_type', label: 'Star Info', description: 'Star type, economy, conflict level' },
  { id: 'planets', label: 'Planet Details', description: 'Hide detailed planet info (shows count only)' }
]

const MAP_VISIBILITY_OPTIONS = [
  { value: 'normal', label: 'Normal', description: 'Fully visible with all hover details' },
  { value: 'point_only', label: 'Point Only', description: 'Shows as a dot but no hover information' },
  { value: 'hidden', label: 'Hidden', description: 'Does not appear on maps at all' }
]

export default function DataRestrictions() {
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin } = auth || {}

  const [systems, setSystems] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // Selection state
  const [selectedIds, setSelectedIds] = useState(new Set())

  // Modal state
  const [editingSystem, setEditingSystem] = useState(null)
  const [showBulkModal, setShowBulkModal] = useState(false)

  // Restriction form state
  const [formHidden, setFormHidden] = useState(false)
  const [formFields, setFormFields] = useState([])
  const [formMapVisibility, setFormMapVisibility] = useState('normal')

  useEffect(() => {
    loadSystems()
  }, [])

  const loadSystems = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/partner/my_systems', { credentials: 'include' })
      if (!res.ok) throw new Error('Failed to load systems')
      const data = await res.json()
      setSystems(data.systems || [])
    } catch (e) {
      console.error('Failed to load systems:', e)
    } finally {
      setLoading(false)
    }
  }

  // Filtered systems based on search
  const filteredSystems = useMemo(() => {
    if (!searchQuery.trim()) return systems
    const q = searchQuery.toLowerCase()
    return systems.filter(s =>
      s.name?.toLowerCase().includes(q) ||
      s.galaxy?.toLowerCase().includes(q) ||
      s.region_name?.toLowerCase().includes(q) ||
      s.discord_tag?.toLowerCase().includes(q)
    )
  }, [systems, searchQuery])

  // Selection handlers
  const toggleSelect = (id) => {
    const newSet = new Set(selectedIds)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    setSelectedIds(newSet)
  }

  const selectAll = () => {
    setSelectedIds(new Set(filteredSystems.map(s => s.id)))
  }

  const clearSelection = () => {
    setSelectedIds(new Set())
  }

  // Open edit modal for single system
  const openEditModal = (system) => {
    setEditingSystem(system)
    if (system.restriction) {
      setFormHidden(system.restriction.is_hidden_from_public)
      setFormFields(system.restriction.hidden_fields || [])
      setFormMapVisibility(system.restriction.map_visibility || 'normal')
    } else {
      setFormHidden(false)
      setFormFields([])
      setFormMapVisibility('normal')
    }
  }

  // Open bulk edit modal
  const openBulkModal = () => {
    setFormHidden(false)
    setFormFields([])
    setFormMapVisibility('normal')
    setShowBulkModal(true)
  }

  // Close modals
  const closeModal = () => {
    setEditingSystem(null)
    setShowBulkModal(false)
  }

  // Toggle field in form
  const toggleField = (fieldId) => {
    if (formFields.includes(fieldId)) {
      setFormFields(formFields.filter(f => f !== fieldId))
    } else {
      setFormFields([...formFields, fieldId])
    }
  }

  // Save single system restriction
  const saveRestriction = async () => {
    if (!editingSystem) return
    setSaving(true)
    try {
      const res = await fetch('/api/data_restrictions', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_id: editingSystem.id,
          is_hidden_from_public: formHidden,
          hidden_fields: formFields,
          map_visibility: formMapVisibility
        })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to save')
      }
      await loadSystems()
      closeModal()
    } catch (e) {
      alert('Failed to save restriction: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  // Remove single system restriction
  const removeRestriction = async () => {
    if (!editingSystem) return
    if (!confirm('Remove all restrictions from this system?')) return
    setSaving(true)
    try {
      const res = await fetch(`/api/data_restrictions/${editingSystem.id}`, {
        method: 'DELETE',
        credentials: 'include'
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to remove')
      }
      await loadSystems()
      closeModal()
    } catch (e) {
      alert('Failed to remove restriction: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  // Bulk save restrictions
  const saveBulkRestrictions = async () => {
    if (selectedIds.size === 0) return
    setSaving(true)
    try {
      const res = await fetch('/api/data_restrictions/bulk', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_ids: Array.from(selectedIds),
          is_hidden_from_public: formHidden,
          hidden_fields: formFields,
          map_visibility: formMapVisibility
        })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to save')
      }
      const result = await res.json()
      alert(`Restrictions applied: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped`)
      await loadSystems()
      setShowBulkModal(false)
      clearSelection()
    } catch (e) {
      alert('Failed to save restrictions: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  // Bulk remove restrictions
  const bulkRemoveRestrictions = async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`Remove restrictions from ${selectedIds.size} systems?`)) return
    setSaving(true)
    try {
      const res = await fetch('/api/data_restrictions/bulk_remove', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_ids: Array.from(selectedIds)
        })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to remove')
      }
      const result = await res.json()
      alert(`Restrictions removed from ${result.removed} systems (${result.skipped} skipped)`)
      await loadSystems()
      clearSelection()
    } catch (e) {
      alert('Failed to remove restrictions: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  if (!isAdmin) {
    return <div className="text-center py-12" style={{ color: 'var(--muted)' }}>Please log in to manage data restrictions.</div>
  }

  // Stats
  const totalSystems = systems.length
  const restrictedCount = systems.filter(s => s.has_restriction).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Data Restrictions</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            Control which data is visible to public viewers. {isSuperAdmin ? 'Viewing all systems.' : 'Viewing your systems.'}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="pill pill-muted">{totalSystems} systems</span>
          <span className="pill pill-amber">{restrictedCount} restricted</span>
        </div>
      </div>

      {/* Search and Actions */}
      <Card className="haven-card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <input
            type="text"
            placeholder="Search systems..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="haven-input flex-1 px-4 py-2"
          />
          <div className="flex gap-2">
            <Button onClick={selectAll} className="haven-btn-ghost" size="sm">Select All</Button>
            <Button onClick={clearSelection} className="haven-btn-ghost" size="sm">Clear</Button>
          </div>
        </div>

        {/* Bulk Actions */}
        {selectedIds.size > 0 && (
          <div className="haven-card mt-4 p-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <span className="font-medium" style={{ color: 'var(--app-primary)' }}>{selectedIds.size} systems selected</span>
            <div className="flex gap-2">
              <Button onClick={openBulkModal} className="haven-btn-primary" size="sm">Apply Restrictions</Button>
              <Button onClick={bulkRemoveRestrictions} variant="danger" size="sm">Remove Restrictions</Button>
            </div>
          </div>
        )}
      </Card>

      {/* Systems List */}
      {loading ? (
        <Card className="haven-card">
          <div className="p-8 text-center" style={{ color: 'var(--muted)' }}>Loading systems...</div>
        </Card>
      ) : filteredSystems.length === 0 ? (
        <Card className="haven-card">
          <div className="p-8 text-center" style={{ color: 'var(--muted)' }}>
            {systems.length === 0 ? 'No systems found.' : 'No systems match your search.'}
          </div>
        </Card>
      ) : (
        <div className="space-y-2">
          {filteredSystems.map(system => (
            <div
              key={system.id}
              className="haven-card haven-card-hover p-3 flex items-center gap-4"
              style={selectedIds.has(system.id) ? { borderColor: 'var(--app-primary)' } : undefined}
            >
              {/* Checkbox */}
              <input
                type="checkbox"
                checked={selectedIds.has(system.id)}
                onChange={() => toggleSelect(system.id)}
                className="w-5 h-5 rounded"
              />

              {/* System Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium truncate">{system.name}</span>
                  <span className="pill pill-muted">{system.galaxy}</span>
                  {isSuperAdmin && system.discord_tag && (
                    <span className="pill pill-purple">{system.discord_tag}</span>
                  )}
                </div>
                <div className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
                  {system.region_name || `Region (${system.region_x}, ${system.region_y}, ${system.region_z})`}
                </div>
              </div>

              {/* Restriction Status */}
              <div className="flex items-center gap-3">
                {system.has_restriction ? (
                  <div className="flex items-center gap-2 flex-wrap">
                    {system.restriction.is_hidden_from_public && (
                      <span className="pill pill-red">HIDDEN</span>
                    )}
                    {system.restriction.hidden_fields?.length > 0 && (
                      <span className="pill pill-yellow">
                        {system.restriction.hidden_fields.length} fields
                      </span>
                    )}
                    {system.restriction.map_visibility !== 'normal' && (
                      <span className="pill pill-amber">
                        {system.restriction.map_visibility === 'hidden' ? 'Map Hidden' : 'Point Only'}
                      </span>
                    )}
                  </div>
                ) : (
                  <span className="text-xs" style={{ color: 'var(--muted)' }}>Public</span>
                )}
                <Button onClick={() => openEditModal(system)} className="haven-btn-ghost" size="sm">
                  Configure
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Single System Edit Modal */}
      {editingSystem && (
        <div className="haven-modal">
          <div className="haven-modal-panel">
            <div className="haven-modal-header">
              <div>
                <div className="text-xl font-bold">Configure Restrictions</div>
                <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>{editingSystem.name}</p>
              </div>
            </div>

            <div className="haven-modal-body space-y-6">
              {/* Hide from public toggle */}
              <div className="haven-card p-4 flex items-center justify-between">
                <div>
                  <div className="font-medium">Hide from Public</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>Completely hide this system from non-owners</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formHidden}
                    onChange={(e) => setFormHidden(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:ring-2 peer-focus:ring-cyan-500 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-600"></div>
                </label>
              </div>

              {/* Field restrictions */}
              <div>
                <h3 className="font-medium mb-3">Hide Specific Fields</h3>
                <div className="space-y-2">
                  {RESTRICTABLE_FIELDS.map(field => (
                    <label
                      key={field.id}
                      className="haven-card haven-card-hover flex items-start gap-3 p-3 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={formFields.includes(field.id)}
                        onChange={() => toggleField(field.id)}
                        className="w-5 h-5 mt-0.5 rounded"
                      />
                      <div>
                        <div className="font-medium">{field.label}</div>
                        <div className="text-sm" style={{ color: 'var(--muted)' }}>{field.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Map visibility */}
              <div>
                <h3 className="font-medium mb-3">Map Visibility</h3>
                <div className="space-y-2">
                  {MAP_VISIBILITY_OPTIONS.map(opt => (
                    <label
                      key={opt.value}
                      className="haven-card haven-card-hover flex items-start gap-3 p-3 cursor-pointer"
                      style={formMapVisibility === opt.value ? { borderColor: 'var(--app-primary)', background: 'var(--app-primary-soft)' } : undefined}
                    >
                      <input
                        type="radio"
                        name="mapVisibility"
                        value={opt.value}
                        checked={formMapVisibility === opt.value}
                        onChange={(e) => setFormMapVisibility(e.target.value)}
                        className="w-5 h-5 mt-0.5"
                      />
                      <div>
                        <div className="font-medium">{opt.label}</div>
                        <div className="text-sm" style={{ color: 'var(--muted)' }}>{opt.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="haven-modal-footer" style={{ justifyContent: 'space-between' }}>
              <Button onClick={removeRestriction} variant="danger" disabled={saving || !editingSystem.has_restriction}>
                Remove All
              </Button>
              <div className="flex gap-2">
                <Button onClick={closeModal} className="haven-btn-ghost" disabled={saving}>Cancel</Button>
                <Button onClick={saveRestriction} className="haven-btn-primary" disabled={saving}>
                  {saving ? 'Saving...' : 'Save'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Edit Modal */}
      {showBulkModal && (
        <div className="haven-modal">
          <div className="haven-modal-panel">
            <div className="haven-modal-header">
              <div>
                <div className="text-xl font-bold">Bulk Apply Restrictions</div>
                <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>Apply to {selectedIds.size} selected systems</p>
              </div>
            </div>

            <div className="haven-modal-body space-y-6">
              {/* Hide from public toggle */}
              <div className="haven-card p-4 flex items-center justify-between">
                <div>
                  <div className="font-medium">Hide from Public</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>Completely hide these systems from non-owners</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formHidden}
                    onChange={(e) => setFormHidden(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:ring-2 peer-focus:ring-cyan-500 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-600"></div>
                </label>
              </div>

              {/* Field restrictions */}
              <div>
                <h3 className="font-medium mb-3">Hide Specific Fields</h3>
                <div className="space-y-2">
                  {RESTRICTABLE_FIELDS.map(field => (
                    <label
                      key={field.id}
                      className="haven-card haven-card-hover flex items-start gap-3 p-3 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={formFields.includes(field.id)}
                        onChange={() => toggleField(field.id)}
                        className="w-5 h-5 mt-0.5 rounded"
                      />
                      <div>
                        <div className="font-medium">{field.label}</div>
                        <div className="text-sm" style={{ color: 'var(--muted)' }}>{field.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Map visibility */}
              <div>
                <h3 className="font-medium mb-3">Map Visibility</h3>
                <div className="space-y-2">
                  {MAP_VISIBILITY_OPTIONS.map(opt => (
                    <label
                      key={opt.value}
                      className="haven-card haven-card-hover flex items-start gap-3 p-3 cursor-pointer"
                      style={formMapVisibility === opt.value ? { borderColor: 'var(--app-primary)', background: 'var(--app-primary-soft)' } : undefined}
                    >
                      <input
                        type="radio"
                        name="bulkMapVisibility"
                        value={opt.value}
                        checked={formMapVisibility === opt.value}
                        onChange={(e) => setFormMapVisibility(e.target.value)}
                        className="w-5 h-5 mt-0.5"
                      />
                      <div>
                        <div className="font-medium">{opt.label}</div>
                        <div className="text-sm" style={{ color: 'var(--muted)' }}>{opt.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="haven-modal-footer">
              <Button onClick={closeModal} className="haven-btn-ghost" disabled={saving}>Cancel</Button>
              <Button onClick={saveBulkRestrictions} className="haven-btn-primary" disabled={saving}>
                {saving ? 'Applying...' : `Apply to ${selectedIds.size} Systems`}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
