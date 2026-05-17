import React, { useEffect, useState, useContext } from 'react'
import { AuthContext } from '../utils/AuthContext'
import { clearPersonalColorCache } from '../utils/usePersonalColor'
import Card from '../components/Card'
import Button from '../components/Button'

/**
 * Settings Page
 * Route: /settings
 * Auth: Feature-gated (settings feature flag) -- any admin role
 *
 * Provides role-dependent settings sections:
 *   - All admins: change password, logout
 *   - Partners: change username, per-session theme, region color for 3D map
 *   - Super admin: global theme, personal submission badge color
 *
 * DB backup/restore + data migration tools were moved to /admin/tools in
 * v1.53.0 — see [AdminTools.jsx](AdminTools.jsx).
 *
 * Key APIs:
 *   GET/POST /api/settings              (global settings + personal color)
 *   GET/PUT  /api/partner/theme          (partner theme)
 *   GET/PUT  /api/partner/region_color   (3D map region color)
 *   POST     /api/change_password
 *   POST     /api/change_username
 */
export default function Settings() {
  const auth = useContext(AuthContext)
  const { isAdmin, isSuperAdmin, isPartner, user, logout } = auth || {}

  const [settings, setSettings] = useState({})
  const [partnerTheme, setPartnerTheme] = useState({})
  const [regionColor, setRegionColor] = useState('#00C2B3')
  const [personalColor, setPersonalColor] = useState('#c026d3')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savingRegionColor, setSavingRegionColor] = useState(false)
  const [savingPersonalColor, setSavingPersonalColor] = useState(false)

  // Change password state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)

  // Change username state (partners)
  const [newUsername, setNewUsername] = useState('')
  const [usernamePassword, setUsernamePassword] = useState('')
  const [changingUsername, setChangingUsername] = useState(false)

  useEffect(() => {
    // Load global settings
    fetch('/api/settings', { credentials: 'include' })
      .then(r => r.json())
      .then(s => {
        setSettings(s || {})
        if (s && s.personal_color) {
          setPersonalColor(s.personal_color)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))

    // Load partner theme and region color if partner
    if (isPartner) {
      fetch('/api/partner/theme', { credentials: 'include' })
        .then(r => r.json())
        .then(data => setPartnerTheme(data.theme || {}))
        .catch(() => {})

      fetch('/api/partner/region_color', { credentials: 'include' })
        .then(r => r.json())
        .then(data => setRegionColor(data.color || '#00C2B3'))
        .catch(() => {})
    }
  }, [isPartner])

  const updateTheme = (k, v) => {
    const theme = { ...(settings.theme || {}), [k]: v }
    setSettings({ ...settings, theme })
    // Apply immediately for preview
    if (k === 'bg') document.documentElement.style.setProperty('--app-bg', v)
    if (k === 'text') document.documentElement.style.setProperty('--app-text', v)
    if (k === 'card') document.documentElement.style.setProperty('--app-card', v)
    if (k === 'primary') document.documentElement.style.setProperty('--app-primary', v)
  }

  const updatePartnerTheme = (k, v) => {
    const theme = { ...partnerTheme, [k]: v }
    setPartnerTheme(theme)
    // Apply immediately for preview
    if (k === 'bg') document.documentElement.style.setProperty('--app-bg', v)
    if (k === 'text') document.documentElement.style.setProperty('--app-text', v)
    if (k === 'card') document.documentElement.style.setProperty('--app-card', v)
    if (k === 'primary') document.documentElement.style.setProperty('--app-primary', v)
  }

  const saveGlobalSettings = async () => {
    setSaving(true)
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      })
      if (!res.ok) throw new Error(await res.text())
      alert('Settings saved successfully!')
    } catch (e) {
      alert('Failed to save settings: ' + e)
    }
    setSaving(false)
  }

  const savePartnerTheme = async () => {
    setSaving(true)
    try {
      const res = await fetch('/api/partner/theme', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme: partnerTheme })
      })
      if (!res.ok) throw new Error(await res.text())
      alert('Theme saved successfully!')
    } catch (e) {
      alert('Failed to save theme: ' + e)
    }
    setSaving(false)
  }

  const saveRegionColor = async () => {
    setSavingRegionColor(true)
    try {
      const res = await fetch('/api/partner/region_color', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ color: regionColor })
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to save')
      }
      alert('Region color saved! The 3D map will now show your regions in this color.')
    } catch (e) {
      alert('Failed to save region color: ' + e.message)
    }
    setSavingRegionColor(false)
  }

  const savePersonalColor = async () => {
    setSavingPersonalColor(true)
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ personal_color: personalColor })
      })
      if (!res.ok) throw new Error(await res.text())
      clearPersonalColorCache() // Clear cache so other components get the new color
      alert('Personal submission color saved!')
    } catch (e) {
      alert('Failed to save personal color: ' + e)
    }
    setSavingPersonalColor(false)
  }

  const changePassword = async () => {
    if (!currentPassword) {
      alert('Please enter your current password')
      return
    }
    if (!newPassword || newPassword.length < 4) {
      alert('New password must be at least 4 characters')
      return
    }
    if (newPassword !== confirmPassword) {
      alert('New passwords do not match')
      return
    }

    setChangingPassword(true)
    try {
      const res = await fetch('/api/change_password', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to change password')
      }

      alert('Password changed successfully! Please log in again with your new password.')
      // Clear form
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      // Log out so user has to re-authenticate with new password
      logout()
    } catch (e) {
      alert('Failed to change password: ' + e.message)
    } finally {
      setChangingPassword(false)
    }
  }

  const changeUsername = async () => {
    if (!usernamePassword) {
      alert('Please enter your current password')
      return
    }
    if (!newUsername || newUsername.length < 3) {
      alert('New username must be at least 3 characters')
      return
    }
    if (newUsername.length > 50) {
      alert('Username must be 50 characters or less')
      return
    }
    // Basic validation - alphanumeric, underscores, hyphens
    if (!/^[a-zA-Z0-9_-]+$/.test(newUsername)) {
      alert('Username can only contain letters, numbers, underscores, and hyphens')
      return
    }

    setChangingUsername(true)
    try {
      const res = await fetch('/api/change_username', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: usernamePassword,
          new_username: newUsername
        })
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to change username')
      }

      alert('Username changed successfully! Please log in again with your new username.')
      // Clear form
      setNewUsername('')
      setUsernamePassword('')
      // Log out so user has to re-authenticate with new username
      logout()
    } catch (e) {
      alert('Failed to change username: ' + e.message)
    } finally {
      setChangingUsername(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg" style={{ color: 'var(--muted)' }}>Loading settings...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold" style={{ color: 'var(--app-primary)' }}>Settings</h1>

      {/* User Info */}
      <Card className="haven-card">
        <div className="p-4">
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>Logged in as</h3>
          <div style={{ color: 'var(--app-text)' }}>
            <p><strong>{user?.displayName || user?.username}</strong></p>
            {isSuperAdmin && <p className="text-sm" style={{ color: 'var(--app-accent-amber)' }}>Super Admin</p>}
            {isPartner && user?.discordTag && <p className="text-sm" style={{ color: 'var(--app-primary)' }}>Partner: {user.discordTag}</p>}
          </div>
          <Button className="haven-btn-ghost mt-3" onClick={logout}>Logout</Button>
        </div>
      </Card>

      {/* Change Password */}
      {isAdmin && (
        <Card className="haven-card">
          <div className="p-4">
            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>Change Password</h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
              Update your password. You will be logged out after changing your password.
            </p>

            <div className="space-y-4 max-w-md">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Current Password</label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={e => setCurrentPassword(e.target.value)}
                  className="w-full"
                  placeholder="Enter current password"
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  className="w-full"
                  placeholder="Enter new password (min 4 characters)"
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Confirm New Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  className="w-full"
                  placeholder="Confirm new password"
                />
              </div>

              <Button
                className="haven-btn-primary"
                onClick={changePassword}
                disabled={changingPassword || !currentPassword || !newPassword || !confirmPassword}
              >
                {changingPassword ? 'Changing...' : 'Change Password'}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Change Username (Partners only) */}
      {isPartner && (
        <Card className="haven-card">
          <div className="p-4">
            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>Change Username</h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
              Update your login username. You will be logged out after changing your username.
            </p>

            <div className="space-y-4 max-w-md">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Current Username</label>
                <p className="font-medium" style={{ color: 'var(--app-text)' }}>{user?.username || ''}</p>
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>New Username</label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={e => setNewUsername(e.target.value)}
                  className="w-full"
                  placeholder="Enter new username (min 3 characters)"
                />
                <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                  Letters, numbers, underscores, and hyphens only
                </p>
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Current Password</label>
                <input
                  type="password"
                  value={usernamePassword}
                  onChange={e => setUsernamePassword(e.target.value)}
                  className="w-full"
                  placeholder="Enter your password to confirm"
                />
              </div>

              <Button
                className="haven-btn-primary"
                onClick={changeUsername}
                disabled={changingUsername || !newUsername || !usernamePassword}
              >
                {changingUsername ? 'Changing...' : 'Change Username'}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Partner Theme Settings */}
      {isPartner && (
        <Card className="haven-card">
          <div className="p-4">
            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>Your Theme</h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
              Customize your view of Haven Control Room. These settings only affect your session.
            </p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Background</label>
                <input
                  type="color"
                  value={partnerTheme.bg || '#1f2937'}
                  onChange={e => updatePartnerTheme('bg', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Text</label>
                <input
                  type="color"
                  value={partnerTheme.text || '#f3f4f6'}
                  onChange={e => updatePartnerTheme('text', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Card</label>
                <input
                  type="color"
                  value={partnerTheme.card || '#374151'}
                  onChange={e => updatePartnerTheme('card', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Primary</label>
                <input
                  type="color"
                  value={partnerTheme.primary || '#06b6d4'}
                  onChange={e => updatePartnerTheme('primary', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
            </div>

            <Button className="haven-btn-primary mt-4" onClick={savePartnerTheme} disabled={saving}>
              {saving ? 'Saving...' : 'Save Your Theme'}
            </Button>
          </div>
        </Card>
      )}

      {/* Partner: Region Color for 3D Map */}
      {isPartner && (
        <Card className="haven-card">
          <div className="p-4">
            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>3D Galaxy Map - Region Color</h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
              Choose a custom color for your community's regions on the 3D galaxy map.
              This color will be visible to everyone viewing the map.
            </p>

            <div className="flex items-center gap-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Region Point Color</label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={regionColor}
                    onChange={e => setRegionColor(e.target.value)}
                    className="w-16 h-10 rounded cursor-pointer"
                    style={{ border: '2px solid var(--border-soft)' }}
                  />
                  <input
                    type="text"
                    value={regionColor}
                    onChange={e => {
                      const val = e.target.value
                      if (/^#[0-9A-Fa-f]{0,6}$/.test(val)) {
                        setRegionColor(val)
                      }
                    }}
                    placeholder="#00C2B3"
                    className="w-28 font-mono text-sm"
                  />
                </div>
              </div>

              {/* Color preview */}
              <div className="flex-1">
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Preview</label>
                <div className="flex items-center gap-2">
                  <div
                    className="w-8 h-8 rounded-full shadow-lg"
                    style={{
                      backgroundColor: regionColor,
                      boxShadow: `0 0 15px ${regionColor}80`
                    }}
                  />
                  <span className="text-sm" style={{ color: 'var(--muted)' }}>
                    This is how your regions will appear on the map
                  </span>
                </div>
              </div>
            </div>

            <Button className="haven-btn-primary mt-4" onClick={saveRegionColor} disabled={savingRegionColor}>
              {savingRegionColor ? 'Saving...' : 'Save Region Color'}
            </Button>
          </div>
        </Card>
      )}

      {/* Super Admin: Global Theme Settings */}
      {isSuperAdmin && (
        <Card className="haven-card">
          <div className="p-4">
            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>Global Theme</h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
              Server-side theme controls the color palette for all users (default).
            </p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Background</label>
                <input
                  type="color"
                  value={(settings.theme && settings.theme.bg) || '#1f2937'}
                  onChange={e => updateTheme('bg', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Text</label>
                <input
                  type="color"
                  value={(settings.theme && settings.theme.text) || '#f3f4f6'}
                  onChange={e => updateTheme('text', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Card</label>
                <input
                  type="color"
                  value={(settings.theme && settings.theme.card) || '#374151'}
                  onChange={e => updateTheme('card', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Primary</label>
                <input
                  type="color"
                  value={(settings.theme && settings.theme.primary) || '#06b6d4'}
                  onChange={e => updateTheme('primary', e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
            </div>

            <Button className="haven-btn-primary mt-4" onClick={saveGlobalSettings} disabled={saving}>
              {saving ? 'Saving...' : 'Save Global Theme'}
            </Button>
          </div>
        </Card>
      )}

      {/* Super Admin: Personal Submission Color */}
      {isSuperAdmin && (
        <Card className="haven-card">
          <div className="p-4">
            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>Personal Submission Badge Color</h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
              Customize the color used for personal submissions (submissions without a community tag).
              This color is visible across the UI where personal badges are displayed.
            </p>

            <div className="flex items-center gap-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Badge Color</label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={personalColor}
                    onChange={e => setPersonalColor(e.target.value)}
                    className="w-16 h-10 rounded cursor-pointer"
                    style={{ border: '2px solid var(--border-soft)' }}
                  />
                  <input
                    type="text"
                    value={personalColor}
                    onChange={e => {
                      const val = e.target.value
                      if (/^#[0-9A-Fa-f]{0,6}$/.test(val)) {
                        setPersonalColor(val)
                      }
                    }}
                    placeholder="#c026d3"
                    className="w-28 font-mono text-sm"
                  />
                </div>
              </div>

              {/* Color preview */}
              <div className="flex-1">
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text)' }}>Preview</label>
                <div className="flex items-center gap-2">
                  <span
                    className="px-2 py-1 rounded text-xs font-semibold text-white"
                    style={{ backgroundColor: personalColor }}
                  >
                    PERSONAL
                  </span>
                  <span className="text-sm" style={{ color: 'var(--muted)' }}>
                    Badge preview
                  </span>
                </div>
              </div>
            </div>

            <Button className="haven-btn-primary mt-4" onClick={savePersonalColor} disabled={savingPersonalColor}>
              {savingPersonalColor ? 'Saving...' : 'Save Personal Color'}
            </Button>
          </div>
        </Card>
      )}

      {/* Pointer to Admin Tools — backup and migrations moved there v1.49.0 */}
      {isSuperAdmin && (
        <Card className="haven-card">
          <div className="p-4 text-sm" style={{ color: 'var(--muted)' }}>
            <strong style={{ color: 'var(--app-text)' }}>Looking for backup / migrations?</strong> Those moved to{' '}
            <a href="/haven-ui/admin/tools" className="hover:underline" style={{ color: 'var(--app-primary)' }}>Admin Tools</a>{' '}
            so destructive operations don't sit next to personal settings.
          </div>
        </Card>
      )}
    </div>
  )
}
