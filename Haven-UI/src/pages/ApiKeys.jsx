import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useNavigate } from 'react-router-dom'
import Card from '../components/Card'
import Button from '../components/Button'
import Modal from '../components/Modal'
import { adminStatus } from '../utils/api'
import { formatDate } from '../hooks/useDateFormat'

/**
 * API Keys Management — Route: /api-keys
 * Auth: Super admin only (checked via adminStatus()).
 *
 * CRUD interface for API keys used by NMS Save Watcher and other integrations.
 * Keys are shown in full only once at creation time; afterwards only the prefix
 * is displayed. Each key can be scoped to a community via discord_tag.
 *
 * API endpoints:
 *   GET    /api/keys           — list all keys
 *   POST   /api/keys           — create new key (returns full key string)
 *   PUT    /api/keys/:id       — edit name, rate limit, discord tag, or reactivate
 *   DELETE /api/keys/:id       — revoke (soft-delete) a key
 *   GET    /api/discord_tags   — community list for tag dropdown
 */
/** @param {Object} props @param {boolean} [props.embedded=false] When true, hides the page title — "+ Create New Key" button stays. */
export default function ApiKeys({ embedded = false }) {
  const navigate = useNavigate()
  const [isAdmin, setIsAdmin] = useState(false)
  const [loading, setLoading] = useState(true)
  const [keys, setKeys] = useState([])
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [viewKeyModalOpen, setViewKeyModalOpen] = useState(false)
  const [newKeyData, setNewKeyData] = useState(null)
  const [actionInProgress, setActionInProgress] = useState(false)
  const [discordTags, setDiscordTags] = useState([])
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingKey, setEditingKey] = useState(null)

  // Form state for creating a new key
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyRateLimit, setNewKeyRateLimit] = useState(200)
  const [newKeyDiscordTag, setNewKeyDiscordTag] = useState('')

  // Form state for editing a key
  const [editKeyName, setEditKeyName] = useState('')
  const [editKeyRateLimit, setEditKeyRateLimit] = useState(200)
  const [editKeyDiscordTag, setEditKeyDiscordTag] = useState('')

  useEffect(() => {
    adminStatus().then(r => {
      setIsAdmin(r.logged_in)
      if (!r.logged_in) {
        alert('Admin authentication required')
        navigate('/systems')
      } else {
        loadKeys()
        loadDiscordTags()
      }
    }).catch(() => {
      alert('Failed to verify admin status')
      navigate('/systems')
    })
  }, [navigate])

  async function loadDiscordTags() {
    try {
      const response = await axios.get('/api/discord_tags')
      setDiscordTags(response.data.tags || [])
    } catch (err) {
      console.error('Failed to load discord tags:', err)
    }
  }

  async function loadKeys() {
    setLoading(true)
    try {
      const response = await axios.get('/api/keys')
      setKeys(response.data.keys || [])
    } catch (err) {
      alert('Failed to load API keys: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  async function createKey() {
    if (!newKeyName.trim()) {
      alert('Please enter a name for the API key')
      return
    }

    setActionInProgress(true)
    try {
      const response = await axios.post('/api/keys', {
        name: newKeyName.trim(),
        rate_limit: newKeyRateLimit,
        permissions: ['submit', 'check_duplicate'],
        discord_tag: newKeyDiscordTag || null
      })

      // Store the new key data to show in the modal
      setNewKeyData(response.data)
      setCreateModalOpen(false)
      setViewKeyModalOpen(true)

      // Reset form
      setNewKeyName('')
      setNewKeyRateLimit(200)
      setNewKeyDiscordTag('')

      // Reload keys list
      loadKeys()
    } catch (err) {
      alert('Failed to create API key: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function revokeKey(keyId, keyName) {
    if (!confirm(`Revoke API key "${keyName}"?\n\nThis will immediately invalidate the key. Any companion apps using it will stop working.`)) {
      return
    }

    setActionInProgress(true)
    try {
      await axios.delete(`/api/keys/${keyId}`)
      alert(`API key "${keyName}" has been revoked.`)
      loadKeys()
    } catch (err) {
      alert('Failed to revoke API key: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  async function reactivateKey(keyId, keyName) {
    setActionInProgress(true)
    try {
      await axios.put(`/api/keys/${keyId}`, { is_active: true })
      alert(`API key "${keyName}" has been reactivated.`)
      loadKeys()
    } catch (err) {
      alert('Failed to reactivate API key: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function openEditModal(key) {
    setEditingKey(key)
    setEditKeyName(key.name)
    setEditKeyRateLimit(key.rate_limit)
    setEditKeyDiscordTag(key.discord_tag || '')
    setEditModalOpen(true)
  }

  async function saveKeyEdits() {
    if (!editKeyName.trim()) {
      alert('Please enter a name for the API key')
      return
    }

    setActionInProgress(true)
    try {
      await axios.put(`/api/keys/${editingKey.id}`, {
        name: editKeyName.trim(),
        rate_limit: editKeyRateLimit,
        discord_tag: editKeyDiscordTag || null
      })
      alert(`API key "${editKeyName}" has been updated.`)
      setEditModalOpen(false)
      setEditingKey(null)
      loadKeys()
    } catch (err) {
      alert('Failed to update API key: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionInProgress(false)
    }
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
      alert('API key copied to clipboard!')
    }).catch(() => {
      alert('Failed to copy to clipboard. Please copy manually.')
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg" style={{ color: 'var(--muted)' }}>Loading API keys...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header — title hidden when embedded (hub provides), button stays */}
      <div className="flex items-center justify-between">
        {!embedded ? (
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--app-primary)' }}>API Keys</h1>
            <p className="mt-1" style={{ color: 'var(--muted)' }}>
              Manage API keys for the NMS Save Watcher companion app and other integrations
            </p>
          </div>
        ) : <div />}
        <Button className="haven-btn-primary" onClick={() => setCreateModalOpen(true)} disabled={actionInProgress}>
          + Create New Key
        </Button>
      </div>

      {/* Info Card */}
      <div className="haven-card p-4">
        <h3 className="font-semibold mb-2" style={{ color: 'var(--app-primary)' }}>About API Keys</h3>
        <ul className="text-sm space-y-1 list-disc list-inside" style={{ color: 'var(--app-text)' }}>
          <li>API keys allow external applications to submit systems to Voyagers Haven</li>
          <li>Submissions via API key go to the pending approval queue (same as manual submissions)</li>
          <li>Each key has its own rate limit (default: 200 requests/hour)</li>
          <li>Keys are shown only once when created - save them securely!</li>
          <li>Revoked keys can be reactivated if needed</li>
        </ul>
      </div>

      {/* Keys List */}
      {keys.length === 0 ? (
        <div className="haven-card p-8 text-center" style={{ color: 'var(--muted)' }}>
          <p className="text-lg mb-2">No API keys yet</p>
          <p className="text-sm">Create an API key to allow the NMS Save Watcher companion app to submit discoveries.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {keys.map(key => (
            <div key={key.id} className="haven-card p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-lg font-semibold" style={{ color: 'var(--app-text)' }}>{key.name}</h3>
                    {key.is_active ? (
                      <span className="pill pill-emerald">Active</span>
                    ) : (
                      <span className="pill pill-red">Revoked</span>
                    )}
                    {key.discord_tag && (
                      <span className={`pill ${key.discord_tag === 'personal' ? 'pill-purple' : 'pill-teal'}`}>
                        {key.discord_tag}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span style={{ color: 'var(--muted)' }}>Key Prefix:</span>
                      <p className="font-mono" style={{ color: 'var(--app-text)' }}>{key.key_prefix}...</p>
                    </div>
                    <div>
                      <span style={{ color: 'var(--muted)' }}>Rate Limit:</span>
                      <p style={{ color: 'var(--app-text)' }}>{key.rate_limit}/hour</p>
                    </div>
                    <div>
                      <span style={{ color: 'var(--muted)' }}>Created:</span>
                      <p style={{ color: 'var(--app-text)' }}>{formatDate(key.created_at)}</p>
                    </div>
                    <div>
                      <span style={{ color: 'var(--muted)' }}>Last Used:</span>
                      <p style={{ color: 'var(--app-text)' }}>{formatDate(key.last_used_at)}</p>
                    </div>
                  </div>

                  <div className="mt-2">
                    <span className="text-sm" style={{ color: 'var(--muted)' }}>Permissions: </span>
                    <span className="text-sm" style={{ color: 'var(--muted)' }}>
                      {(key.permissions || []).join(', ') || 'None'}
                    </span>
                  </div>
                </div>

                <div className="flex gap-2 ml-4">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => openEditModal(key)}
                    disabled={actionInProgress}
                  >
                    Edit
                  </Button>
                  {key.is_active ? (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => revokeKey(key.id, key.name)}
                      disabled={actionInProgress}
                    >
                      Revoke
                    </Button>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => reactivateKey(key.id, key.name)}
                      disabled={actionInProgress}
                    >
                      Reactivate
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Key Modal */}
      <Modal isOpen={createModalOpen} onClose={() => setCreateModalOpen(false)} title="Create API Key">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
              Key Name *
            </label>
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g., Parker's Companion App"
              className="haven-input w-full px-3 py-2"
            />
            <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>A descriptive name to identify this key</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
              Rate Limit (requests/hour)
            </label>
            <input
              type="number"
              value={newKeyRateLimit}
              onChange={(e) => setNewKeyRateLimit(parseInt(e.target.value) || 200)}
              min="1"
              max="1000"
              className="haven-input w-full px-3 py-2"
            />
            <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>Maximum submissions per hour (default: 200)</p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
              Discord Community Tag
            </label>
            <select
              value={newKeyDiscordTag}
              onChange={(e) => setNewKeyDiscordTag(e.target.value)}
              className="haven-input w-full px-3 py-2"
            >
              <option value="">-- Select a tag --</option>
              <option value="personal">Personal</option>
              {discordTags.map(t => (
                <option key={t.tag} value={t.tag}>{t.name} ({t.tag})</option>
              ))}
            </select>
            <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>Submissions via this key will be auto-tagged with this community</p>
          </div>

          <div className="flex justify-end gap-3 pt-4" style={{ borderTop: '1px solid var(--border-soft)' }}>
            <Button variant="secondary" className="haven-btn-ghost" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button className="haven-btn-primary" onClick={createKey} disabled={actionInProgress || !newKeyName.trim()}>
              {actionInProgress ? 'Creating...' : 'Create Key'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* View New Key Modal */}
      <Modal isOpen={viewKeyModalOpen} onClose={() => setViewKeyModalOpen(false)} title="API Key Created">
        {newKeyData && (
          <div className="space-y-4">
            <div className="haven-card p-3" style={{ borderColor: 'var(--app-accent-amber)' }}>
              <div className="flex items-start gap-2">
                <span className="text-xl" style={{ color: 'var(--app-accent-amber)' }}>⚠️</span>
                <div>
                  <p className="font-semibold" style={{ color: 'var(--app-accent-amber)' }}>Save this key now!</p>
                  <p className="text-sm" style={{ color: 'var(--app-text)' }}>
                    This is the only time the full key will be shown. Store it securely.
                  </p>
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text)' }}>
                Your API Key
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newKeyData.key}
                  readOnly
                  className="haven-input flex-1 px-3 py-2 font-mono text-sm"
                  style={{ color: 'var(--app-primary)' }}
                />
                <Button className="haven-btn-primary" onClick={() => copyToClipboard(newKeyData.key)}>
                  Copy
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span style={{ color: 'var(--muted)' }}>Name:</span>
                <p style={{ color: 'var(--app-text)' }}>{newKeyData.name}</p>
              </div>
              <div>
                <span style={{ color: 'var(--muted)' }}>Rate Limit:</span>
                <p style={{ color: 'var(--app-text)' }}>{newKeyData.rate_limit}/hour</p>
              </div>
              <div>
                <span style={{ color: 'var(--muted)' }}>Discord Tag:</span>
                <p style={{ color: 'var(--app-text)' }}>{newKeyData.discord_tag || 'None'}</p>
              </div>
            </div>

            <div className="haven-card p-4 text-sm">
              <p className="mb-2" style={{ color: 'var(--muted)' }}>To use this key with the NMS Save Watcher companion app:</p>
              <ol className="list-decimal list-inside space-y-1" style={{ color: 'var(--app-text)' }}>
                <li>Open the companion app's web dashboard</li>
                <li>Go to Settings</li>
                <li>Paste this API key in the API Key field</li>
                <li>Save your settings</li>
              </ol>
            </div>

            <div className="flex justify-end pt-4" style={{ borderTop: '1px solid var(--border-soft)' }}>
              <Button className="haven-btn-primary" onClick={() => setViewKeyModalOpen(false)}>
                I've Saved the Key
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Edit Key Modal */}
      <Modal isOpen={editModalOpen} onClose={() => setEditModalOpen(false)} title="Edit API Key">
        {editingKey && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
                Key Name *
              </label>
              <input
                type="text"
                value={editKeyName}
                onChange={(e) => setEditKeyName(e.target.value)}
                className="haven-input w-full px-3 py-2"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
                Rate Limit (requests/hour)
              </label>
              <input
                type="number"
                value={editKeyRateLimit}
                onChange={(e) => setEditKeyRateLimit(parseInt(e.target.value) || 200)}
                min="1"
                max="1000"
                className="haven-input w-full px-3 py-2"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>
                Discord Community Tag
              </label>
              <select
                value={editKeyDiscordTag}
                onChange={(e) => setEditKeyDiscordTag(e.target.value)}
                className="haven-input w-full px-3 py-2"
              >
                <option value="">-- No tag --</option>
                <option value="personal">Personal</option>
                {discordTags.map(t => (
                  <option key={t.tag} value={t.tag}>{t.name} ({t.tag})</option>
                ))}
              </select>
              <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>Submissions via this key will be auto-tagged with this community</p>
            </div>

            <div className="text-sm" style={{ color: 'var(--muted)' }}>
              <span style={{ color: 'var(--muted)' }}>Key Prefix:</span> {editingKey.key_prefix}...
            </div>

            <div className="flex justify-end gap-3 pt-4" style={{ borderTop: '1px solid var(--border-soft)' }}>
              <Button variant="secondary" className="haven-btn-ghost" onClick={() => setEditModalOpen(false)}>
                Cancel
              </Button>
              <Button className="haven-btn-primary" onClick={saveKeyEdits} disabled={actionInProgress || !editKeyName.trim()}>
                {actionInProgress ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
