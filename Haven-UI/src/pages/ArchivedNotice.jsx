import React from 'react'
import { Link } from 'react-router-dom'

/**
 * /archived-notice — shown to users whose civilization has been archived.
 * Publicly accessible (no auth gate).
 */
export default function ArchivedNotice() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center space-y-4">
        <div className="text-5xl mb-2">
          <span role="img" aria-label="archive">&#128451;</span>
        </div>
        <h1 className="text-2xl font-bold">Civilization Archived</h1>
        <p className="opacity-80">
          The civilization you were part of has been archived by a super admin.
          Your submissions and data are preserved but are not publicly visible
          while the archive is in effect.
        </p>
        <p className="opacity-60 text-sm">
          If you believe this was done in error or have questions, please
          contact a super admin or reach out on Discord.
        </p>
        <div className="pt-4">
          <Link
            to="/systems"
            className="inline-block px-4 py-2 rounded font-medium"
            style={{
              backgroundColor: 'var(--app-primary, #00C2B3)',
              color: '#fff',
            }}
          >
            Go to Systems
          </Link>
        </div>
      </div>
    </div>
  )
}
