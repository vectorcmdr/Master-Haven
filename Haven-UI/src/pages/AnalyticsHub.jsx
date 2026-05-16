import React, { useState, useContext, lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AuthContext } from '../utils/AuthContext'

const Analytics = lazy(() => import('./Analytics'))
const PartnerAnalytics = lazy(() => import('./PartnerAnalytics'))
const Events = lazy(() => import('./Events'))

/**
 * Analytics Hub — Route: /analytics-hub
 *
 * Tabbed shell that consolidates the three admin analytics pages into one
 * destination. Each tab mounts the corresponding existing page, so this is
 * additive — the original /analytics, /partner-analytics, /events routes
 * stay live during the migration.
 *
 * Tabs:
 *   - Overview    → PartnerAnalytics (combined systems + discoveries)
 *   - By Source   → Analytics (manual vs Haven Extractor split)
 *   - Events      → Events (competitions + per-event leaderboards)
 *
 * The active tab is persisted via the ?tab= URL param so a deep link
 * (e.g., /analytics-hub?tab=events) lands directly on the right view.
 */
const TABS = [
  { key: 'overview', label: 'Overview', desc: 'Submissions + discoveries combined' },
  { key: 'source', label: 'By Source', desc: 'Manual vs Haven Extractor' },
  { key: 'events', label: 'Events', desc: 'Competitions + leaderboards' },
]

export default function AnalyticsHub() {
  const [searchParams, setSearchParams] = useSearchParams()
  const auth = useContext(AuthContext)
  const initialTab = searchParams.get('tab') || 'overview'
  const [activeTab, setActiveTab] = useState(TABS.some(t => t.key === initialTab) ? initialTab : 'overview')

  const handleTab = (key) => {
    setActiveTab(key)
    setSearchParams({ tab: key }, { replace: true })
  }

  if (auth.loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-400">Loading...</div>
      </div>
    )
  }

  return (
    <div className="-mx-3 sm:-mx-6 -mt-3 sm:-mt-6">
      {/* Hub header — sits above the embedded page's own header.
          Negative margin scoped per breakpoint (container has px-3 on
          phones, px-6 on sm+); pre-fix this over-pulled and caused
          horizontal scroll on mobile. */}
      <div
        className="px-6 pt-4 pb-3 border-b"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0.03), transparent)',
          borderColor: 'rgba(255,255,255,0.08)',
        }}
      >
        <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
          <div>
            <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>Analytics Hub</h1>
            <p className="text-xs" style={{ color: 'var(--app-text)', opacity: 0.55 }}>
              Unified view of submissions, discoveries, and community events
            </p>
          </div>
        </div>
        {/* Tab strip */}
        <div className="flex items-center gap-1 flex-wrap">
          {TABS.map(t => {
            const active = activeTab === t.key
            return (
              <button
                key={t.key}
                onClick={() => handleTab(t.key)}
                className="px-4 py-2 rounded-t-lg text-sm font-medium transition-colors border-b-2"
                style={{
                  borderColor: active ? 'var(--app-primary)' : 'transparent',
                  color: active ? 'var(--app-primary)' : 'var(--app-text)',
                  background: active ? 'rgba(0, 194, 179, 0.08)' : 'transparent',
                  opacity: active ? 1 : 0.65,
                }}
                title={t.desc}
              >
                {t.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Tab body — each tab mounts an existing page in embedded mode so
          its own outer wrapper + page title are skipped (no double chrome). */}
      <div className="p-6">
        <Suspense fallback={
          <div className="flex items-center justify-center min-h-64">
            <div className="text-lg text-gray-400">Loading tab...</div>
          </div>
        }>
          {activeTab === 'overview' && <PartnerAnalytics embedded />}
          {activeTab === 'source' && <Analytics embedded />}
          {activeTab === 'events' && <Events embedded />}
        </Suspense>
      </div>
    </div>
  )
}
