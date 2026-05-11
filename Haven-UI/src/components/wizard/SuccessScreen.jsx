import React from 'react'
import Button from '../Button'

// Wizard v1 post-submit success screen (mockup #v11-post-submit-view 5956,
// v11DoSubmit 10050, v11SubmitAnother 10070).
//
// Replaces the pre-submit pane after a successful submit. Shows:
//   - Success message + submission id
//   - Rank delta (#47 → #44 (+3))    [from leaderboard before/after]
//   - Streak count
//   - Conditional achievement chip (e.g. "First Pirate System")
//   - Card preview (optional poster URL)
//   - Submit Another (resets but preserves identity)
//   - View Leaderboard
//
// Props:
//   result: { submission_id, system_name, status, rankDelta?, streak?, achievement? }
//   onSubmitAnother
//   onViewLeaderboard
//   onViewSystem (only when admin direct save → got a system_id)
export default function SuccessScreen({ result, onSubmitAnother, onViewLeaderboard, onViewSystem }) {
  if (!result) return null
  const isPending = result.status === 'pending' || (result.submission_id && !result.system_id)
  return (
    <div
      className="rounded-xl p-6 sm:p-8 max-w-2xl mx-auto text-center"
      style={{ backgroundColor: 'var(--app-card)', border: '2px solid var(--app-primary)' }}
    >
      <div className="text-5xl mb-3">🎉</div>
      <h2 className="text-2xl font-bold mb-2">
        {isPending ? 'Submitted for Approval' : 'System Saved'}
      </h2>
      <p className="opacity-80 mb-6">
        <span className="font-semibold">{result.system_name || 'Your system'}</span>
        {isPending ? ' is in the review queue.' : ' is live in Haven.'}
      </p>

      {(result.rankDelta || result.streak || result.achievement) && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6 text-left">
          {result.rankDelta && (
            <Stat label="Rank" value={result.rankDelta} />
          )}
          {typeof result.streak === 'number' && (
            <Stat label="Streak" value={`${result.streak} 🔥`} />
          )}
          {result.achievement && (
            <Stat label="Unlocked" value={`★ ${result.achievement}`} accent />
          )}
        </div>
      )}

      <div className="flex flex-wrap justify-center gap-3">
        <Button onClick={onSubmitAnother}>Submit Another</Button>
        {onViewSystem && result.system_id && (
          <Button variant="ghost" onClick={onViewSystem}>View System</Button>
        )}
        <Button variant="ghost" onClick={onViewLeaderboard}>View Leaderboard</Button>
      </div>

      <p className="text-xs opacity-60 mt-6">
        Identity preserved (community, username, expedition) — just enter the next set of glyphs.
      </p>
    </div>
  )
}

function Stat({ label, value, accent }) {
  return (
    <div
      className="rounded p-3"
      style={{
        backgroundColor: 'var(--app-bg)',
        border: `1px solid ${accent ? 'var(--app-accent-amber)' : 'var(--app-accent-3)'}`,
      }}
    >
      <div className="text-[10px] uppercase tracking-wider opacity-60">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  )
}
