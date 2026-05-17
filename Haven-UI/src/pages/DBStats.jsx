import React, { useEffect, useState, useContext } from 'react'
import { AuthContext } from '../utils/AuthContext'

/**
 * Database Statistics — Route: /db_stats
 * Auth: Public (anyone can view). Display adapts to user role:
 *   - Public: global aggregate counts only
 *   - Partner/Sub-admin: community-scoped counts (filtered by discord_tag server-side)
 *   - Super admin: categorized view with admin-only stats (api_keys, audit entries, etc.)
 *
 * API endpoint:
 *   GET /api/db_stats — returns stats object filtered by the caller's session role
 */

// Format stat labels for display
function formatLabel(key) {
  // Check for custom labels first
  if (customLabels[key]) return customLabels[key]
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

// Format large numbers with commas
function formatNumber(num) {
  return num.toLocaleString()
}

// Custom labels for specific stats
const customLabels = {
  'total_regions': 'Named Regions',
  'populated_regions': 'Populated Regions',
  'regions': 'Named Regions'
}

// Group stats keys into named categories for the super admin's sectioned layout.
// Returns null for non-super-admin users (they get a flat grid instead).
function categorizeStats(stats, userType) {
  if (userType === 'super_admin') {
    return {
      'Core Data': ['total_systems', 'total_planets', 'total_moons', 'populated_regions', 'total_regions', 'total_space_stations', 'total_planet_pois', 'total_discoveries', 'unique_galaxies'],
      'Administration': ['partner_accounts', 'sub_admin_accounts', 'api_keys', 'active_communities'],
      'Pending Approvals': ['pending_systems', 'pending_region_names', 'pending_edit_requests'],
      'Audit & Activity': ['approval_audit_entries', 'activity_log_entries', 'data_restrictions']
    }
  }
  return null
}

export default function DBStats() {
  const auth = useContext(AuthContext)
  const { isSuperAdmin, isPartner, isSubAdmin, user } = auth || {}
  const [stats, setStats] = useState(null)
  const [discordTag, setDiscordTag] = useState(null)
  const [userType, setUserType] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // All users use the same endpoint - backend filters by permission
    fetch('/api/db_stats', { credentials: 'include' })
      .then(r => r.json())
      .then(j => {
        setStats(j.stats || null)
        setDiscordTag(j.discord_tag || null)
        setUserType(j.user_type || 'public')
      })
      .catch(() => setStats(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg" style={{ color: 'var(--muted)' }}>Loading statistics...</div>
      </div>
    )
  }

  const categories = categorizeStats(stats, userType)
  const isPartnerOrSubAdmin = userType === 'partner' || userType === 'sub_admin'

  // Get title based on user type
  const getTitle = () => {
    if (userType === 'super_admin') return 'Admin Dashboard'
    if (isPartnerOrSubAdmin && discordTag) return `${discordTag} Statistics`
    return 'Database Statistics'
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--app-primary)' }}>
        {getTitle()}
      </h2>

      {/* Partner/Sub-admin info banner */}
      {isPartnerOrSubAdmin && discordTag && (
        <div className="haven-card p-4 mb-4" style={{ borderColor: 'var(--app-primary)' }}>
          <p className="text-sm" style={{ color: 'var(--app-text)' }}>
            Showing statistics for your community: <strong style={{ color: 'var(--app-primary)' }}>{discordTag}</strong>
          </p>
        </div>
      )}

      {/* Public user info */}
      {userType === 'public' && (
        <div className="haven-card p-4 mb-4" style={{ borderColor: 'var(--app-primary)' }}>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>
            Showing global database statistics. Log in to see community-specific stats.
          </p>
        </div>
      )}

      {stats ? (
        <>
          {/* Super Admin: Categorized view */}
          {userType === 'super_admin' && categories ? (
            <div className="space-y-6">
              {Object.entries(categories).map(([category, keys]) => {
                const categoryStats = keys.filter(k => stats[k] !== undefined)
                if (categoryStats.length === 0) return null

                return (
                  <div key={category}>
                    <h3 className="text-lg font-semibold mb-3 pb-2" style={{ color: 'var(--app-text)', borderBottom: '1px solid var(--border-soft)' }}>
                      {category}
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                      {categoryStats.map(k => (
                        <div key={k} className="haven-card haven-card-hover p-5">
                          <div className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>{formatNumber(stats[k])}</div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>{formatLabel(k)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            /* Partner/Sub-admin/Public: Simple grid */
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {Object.entries(stats).map(([k, v]) => (
                <div key={k} className="haven-card haven-card-hover p-5">
                  <div className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>{formatNumber(v)}</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>{formatLabel(k)}</div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div style={{ color: 'var(--muted)' }}>No statistics available.</div>
      )}

      {/* Partner/Sub-admin info footer */}
      {isPartnerOrSubAdmin && discordTag && (
        <div className="haven-card p-4 mt-6">
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--app-text)' }}>About Your Statistics</h3>
          <ul className="text-sm space-y-1 list-disc list-inside" style={{ color: 'var(--muted)' }}>
            <li>These statistics only include systems tagged with {discordTag}</li>
            <li>Planets, moons, and POIs are counted from your community's systems</li>
            <li>Create more systems or request the admin to tag existing systems with your community tag</li>
          </ul>
        </div>
      )}
    </div>
  )
}
