import { useEffect, useState } from 'react'

// First-visit splash screen: shows the NMS-styled teaser flyer for 3 seconds,
// then fades out. After the first visit, a localStorage flag suppresses it so
// returning visitors land straight on the site. ?splash=1 in the URL forces it
// (handy for sharing the dramatic intro, and for me when iterating on the look).
const STORAGE_KEY = 'gf-splash-seen-v1'
const VISIBLE_MS = 3000
const FADE_MS = 600

export default function Splash() {
  const url = typeof window !== 'undefined' ? new URL(window.location.href) : null
  const force = url?.searchParams.get('splash') === '1'
  const seen = typeof window !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : '1'

  const [phase, setPhase] = useState(() => {
    if (force) return 'visible'
    if (seen) return 'gone'
    return 'visible'
  })

  useEffect(() => {
    if (phase !== 'visible') return
    const fadeAt = setTimeout(() => setPhase('fading'), VISIBLE_MS)
    const goneAt = setTimeout(() => {
      setPhase('gone')
      try { localStorage.setItem(STORAGE_KEY, '1') } catch {}
    }, VISIBLE_MS + FADE_MS)
    return () => {
      clearTimeout(fadeAt)
      clearTimeout(goneAt)
    }
  }, [phase])

  // Esc / click skips the splash.
  useEffect(() => {
    if (phase === 'gone') return
    const skip = () => {
      setPhase('fading')
      setTimeout(() => {
        setPhase('gone')
        try { localStorage.setItem(STORAGE_KEY, '1') } catch {}
      }, FADE_MS)
    }
    const onKey = (e) => { if (e.key === 'Escape') skip() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase])

  if (phase === 'gone') return null

  const onClick = () => {
    setPhase('fading')
    setTimeout(() => {
      setPhase('gone')
      try { localStorage.setItem(STORAGE_KEY, '1') } catch {}
    }, FADE_MS)
  }

  return (
    <div
      className={`splash-overlay ${phase === 'fading' ? 'fading' : ''}`}
      onClick={onClick}
      role="dialog"
      aria-label="Welcome to the Grand Festival"
    >
      <picture className="splash-flyer-wrap">
        <source media="(max-width: 700px)" srcSet="/branding/teaser-flyer-small.jpg" />
        <img
          className="splash-flyer"
          src="/branding/teaser-flyer.jpg"
          alt="1st Annual Grand Festival 2026 — No Man's Sky — June 19–21"
        />
      </picture>
      <div className="splash-skip">tap or press esc to skip</div>
    </div>
  )
}
