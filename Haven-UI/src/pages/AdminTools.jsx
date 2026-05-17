import React, { useState, useContext } from 'react'
import { AuthContext } from '../utils/AuthContext'
import Card from '../components/Card'
import Button from '../components/Button'

/**
 * Admin Tools — Route: /admin/tools
 * Auth: Super admin only.
 *
 * Houses one-shot operations that were previously co-located with personal
 * settings in /settings — DB backup, hub-tag migration, and future ops.
 * Separated because these are destructive / hard-to-reverse and shouldn't
 * sit next to "change my password."
 *
 * Each section uses a confirmation prompt before executing.
 */
export default function AdminTools() {
  const auth = useContext(AuthContext)
  const { isSuperAdmin } = auth || {}

  const [backupResult, setBackupResult] = useState(null)
  const [backupBusy, setBackupBusy] = useState(false)
  const [migrating, setMigrating] = useState(false)
  const [migrateResult, setMigrateResult] = useState(null)

  if (auth.loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading...</div>
      </div>
    )
  }

  if (!isSuperAdmin) {
    return (
      <div className="p-6">
        <div className="text-red-400">Super admin access required.</div>
      </div>
    )
  }

  const doBackup = async () => {
    if (!confirm('Create a database backup now? This may take a few seconds on production.')) return
    setBackupBusy(true)
    setBackupResult(null)
    try {
      const res = await fetch('/api/backup', { method: 'POST', credentials: 'include' })
      if (!res.ok) throw new Error(await res.text())
      const j = await res.json()
      setBackupResult({ ok: true, path: j.backup_path, at: new Date().toLocaleString() })
    } catch (e) {
      setBackupResult({ ok: false, error: String(e) })
    } finally {
      setBackupBusy(false)
    }
  }

  const migrateHubTags = async () => {
    if (!confirm(
      'Hub Tag Migration\n\n' +
      'This will rename systems that have "HUB Tag:" in their description to use the hub tag as the system name. ' +
      'The original name will be preserved in the notes.\n\n' +
      'Continue?'
    )) return
    setMigrating(true)
    setMigrateResult(null)
    try {
      const res = await fetch('/api/migrate_hub_tags', { method: 'POST', credentials: 'include' })
      if (!res.ok) throw new Error(await res.text())
      const j = await res.json()
      setMigrateResult({ ok: true, updated: j.updated, found: j.total_found, at: new Date().toLocaleString() })
    } catch (e) {
      setMigrateResult({ ok: false, error: String(e) })
    } finally {
      setMigrating(false)
    }
  }

  return (
    <div className="-mx-3 sm:-mx-6 -mt-3 sm:-mt-6">
      {/* Hub header — uses shared .hub-header utility (matches AnalyticsHub / AccessControl). */}
      <div className="hub-header">
        <h1 className="hub-header-title">Admin Tools</h1>
        <p className="hub-header-subtitle">
          One-shot operations — destructive or hard to reverse. Read each prompt before confirming.
        </p>
      </div>
      <div className="p-6 space-y-6">

      {/* Database backup */}
      <Card className="haven-card">
        <div className="p-4">
          <h3 className="text-lg font-semibold mb-2">Database Backup</h3>
          <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
            Snapshot the live SQLite database to a timestamped file on the server. Safe to run anytime.
          </p>
          <Button onClick={doBackup} disabled={backupBusy}>
            {backupBusy ? 'Creating backup...' : 'Create Backup'}
          </Button>
          {backupResult && (
            <div className="mt-3 text-sm">
              {backupResult.ok ? (
                <div className="text-green-400">
                  ✓ Backup created at <span className="font-mono">{backupResult.path}</span>
                  <div className="text-xs" style={{ color: 'var(--muted)' }}>{backupResult.at}</div>
                </div>
              ) : (
                <div className="text-red-400">✗ {backupResult.error}</div>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Data migrations */}
      <Card className="haven-card">
        <div className="p-4">
          <h3 className="text-lg font-semibold mb-2">Data Migrations</h3>
          <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
            One-time data fixes. Each migration is idempotent but check the description before running.
          </p>

          <div className="space-y-4">
            <div className="pt-4 hairline">
              <h4 className="text-sm font-medium mb-1">Hub Tag → Name</h4>
              <p className="text-xs mb-3" style={{ color: 'var(--muted)' }}>
                Renames systems that have "HUB Tag:" in their description to use the hub tag as the display name.
                The original system name will be preserved in the notes as "New Name:".
              </p>
              <Button onClick={migrateHubTags} disabled={migrating}>
                {migrating ? 'Migrating...' : 'Migrate Hub Tags to Names'}
              </Button>
              {migrateResult && (
                <div className="mt-3 text-sm">
                  {migrateResult.ok ? (
                    <div className="text-green-400">
                      ✓ Migration complete. Updated {migrateResult.updated} of {migrateResult.found} matching systems.
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>{migrateResult.at}</div>
                    </div>
                  ) : (
                    <div className="text-red-400">✗ {migrateResult.error}</div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </Card>

        {/* Placeholder for future tools */}
        <Card className="haven-card">
          <div className="p-4 text-sm" style={{ color: 'var(--muted)' }}>
            <strong>Future tools:</strong> WAL checkpoint, VACUUM, schema-migration history, etc. can be wired in here.
          </div>
        </Card>
      </div>
    </div>
  )
}
