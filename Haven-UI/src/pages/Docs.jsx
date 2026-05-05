import React from 'react'
import { Link } from 'react-router-dom'
import manifest from '../data/docs/manifest.json'

/**
 * Docs — Route: /docs
 * Auth: Public.
 *
 * Hub page listing every doc in src/data/docs/manifest.json. Each card links
 * to /docs/<slug> which renders the corresponding .md file.
 *
 * Color accents map to manifest entry's `accent` field:
 *   teal   = --app-primary       (member-facing)
 *   amber  = --app-accent-amber  (leadership)
 *   violet = --app-accent-2      (advanced / power user)
 */

const ACCENT = {
  teal:   { var: 'var(--app-primary)',      rgba: 'rgba(0,194,179,0.4)',  bg: 'rgba(0,194,179,0.1)' },
  amber:  { var: 'var(--app-accent-amber)', rgba: 'rgba(255,180,76,0.4)', bg: 'rgba(255,180,76,0.1)' },
  violet: { var: 'var(--app-accent-2)',     rgba: 'rgba(157,78,221,0.4)', bg: 'rgba(157,78,221,0.1)' },
}

export default function Docs() {
  const docs = manifest.docs || []

  return (
    <div className="max-w-5xl mx-auto" style={{ color: 'var(--app-text)' }}>
      {/* HERO */}
      <section className="text-center py-16 md:py-20">
        <div
          className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-6 font-mono text-[11px] uppercase"
          style={{
            border: '1px solid rgba(255,255,255,0.12)',
            background: 'rgba(255,255,255,0.02)',
            color: 'var(--app-accent-2)',
            letterSpacing: '0.18em',
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: 'var(--app-accent-2)', boxShadow: '0 0 8px var(--app-accent-2)' }}
          />
          Documentation
        </div>

        <h1 className="text-5xl md:text-6xl font-bold mb-3 leading-tight tracking-tight">
          Haven{' '}
          <span
            style={{
              background: 'linear-gradient(120deg, var(--app-primary), var(--app-accent-2))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Docs
          </span>
        </h1>

        <p className="text-sm md:text-base max-w-2xl mx-auto" style={{ color: 'var(--muted)' }}>
          A handful of guides depending on who you are. Read whichever one fits.
        </p>
      </section>

      {/* DOC LIST */}
      <section className="pb-12 space-y-4">
        {docs.map((doc) => (
          <DocCard key={doc.slug} doc={doc} />
        ))}
      </section>

      {/* CHANGELOG SHORTCUT — Haven's Changelog page is preserved at /changelog */}
      <section className="pb-16">
        <div
          className="rounded-xl p-6 md:p-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4"
          style={{
            background: 'linear-gradient(180deg, var(--app-card), rgba(255,255,255,0.01))',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <div>
            <div
              className="font-mono text-[10px] uppercase mb-2"
              style={{ color: 'var(--app-accent-2)', letterSpacing: '0.18em' }}
            >
              Looking for the Changelog?
            </div>
            <h3 className="text-lg md:text-xl font-semibold leading-snug" style={{ color: 'var(--app-text)' }}>
              The full Voyager's Haven story page lives on its own.
            </h3>
            <p className="text-sm mt-1.5 leading-relaxed" style={{ color: 'rgba(255,255,255,0.78)' }}>
              What we've built, what we're shipping, what's still being made. It hasn't moved.
            </p>
          </div>
          <Link
            to="/changelog"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full font-semibold text-sm whitespace-nowrap transition-transform hover:-translate-y-0.5 self-start md:self-auto"
            style={{
              background: 'rgba(157,78,221,0.12)',
              color: 'var(--app-accent-2)',
              border: '1px solid rgba(157,78,221,0.4)',
            }}
          >
            View the Changelog →
          </Link>
        </div>
      </section>

      {/* FOOTER */}
      <footer
        className="text-center pt-12 pb-12 mt-4 border-t"
        style={{ borderColor: 'rgba(255,255,255,0.08)' }}
      >
        <p className="max-w-xl mx-auto mb-6 text-sm md:text-base leading-relaxed" style={{ color: 'var(--muted)' }}>
          Have a question that isn't answered here? Ask in the Discord — real members read it every day.
        </p>
        <a
          href="https://discord.gg/2PbhNPdDQ"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 px-7 py-3 rounded-full font-semibold text-sm transition-transform hover:-translate-y-0.5"
          style={{
            background: 'var(--app-primary)',
            color: 'var(--app-bg)',
            boxShadow: '0 0 30px rgba(0,194,179,0.25)',
          }}
        >
          Join the Discord →
        </a>
      </footer>
    </div>
  )
}

function DocCard({ doc }) {
  const accent = ACCENT[doc.accent] || ACCENT.teal
  return (
    <Link
      to={`/docs/${doc.slug}`}
      className="group flex items-start gap-5 rounded-xl p-6 md:p-7 transition-all hover:-translate-y-0.5"
      style={{
        background: 'linear-gradient(180deg, var(--app-card), rgba(255,255,255,0.01))',
        border: '1px solid rgba(255,255,255,0.08)',
        color: 'var(--app-text)',
        textDecoration: 'none',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = accent.rgba }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
    >
      {/* Icon tile */}
      <div
        className="flex-shrink-0 w-14 h-14 md:w-16 md:h-16 rounded-xl flex items-center justify-center text-2xl md:text-3xl"
        style={{
          background: accent.bg,
          border: `1px solid ${accent.rgba}`,
        }}
        aria-hidden="true"
      >
        {doc.icon}
      </div>

      {/* Body */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="font-mono text-[10px] uppercase font-medium"
            style={{ color: accent.var, letterSpacing: '0.18em' }}
          >
            {doc.eyebrow}
          </span>
        </div>
        <h3 className="text-xl md:text-2xl font-semibold tracking-tight mt-1.5">{doc.title}</h3>
        <p className="text-sm md:text-[15px] leading-relaxed mt-2" style={{ color: 'rgba(255,255,255,0.78)' }}>
          {doc.blurb}
        </p>
        <div
          className="flex items-center gap-3 mt-3.5 font-mono text-[11px]"
          style={{ color: 'var(--muted)' }}
        >
          <span>~{doc.readMinutes} min read</span>
          <span className="w-1 h-1 rounded-full opacity-60" style={{ background: 'var(--muted)' }} />
          <span>{doc.audience}</span>
        </div>
      </div>

      {/* Arrow */}
      <div
        className="flex-shrink-0 self-center text-2xl transition-transform group-hover:translate-x-0.5"
        style={{ color: accent.var }}
        aria-hidden="true"
      >
        →
      </div>
    </Link>
  )
}
