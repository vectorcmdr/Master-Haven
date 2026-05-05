import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, Navigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import manifest from '../data/docs/manifest.json'

/**
 * DocPage — Route: /docs/:slug
 * Auth: Public.
 *
 * Renders a single doc from src/data/docs/<slug>.md, with a left sidebar that
 * auto-generates from the doc's H2 headings. Active section is tracked via
 * IntersectionObserver (scrollspy).
 *
 * Markdown bodies live in src/data/docs/*.md. They're loaded eagerly via Vite's
 * import.meta.glob with `?raw` so each file ships as a string in the build.
 */

const DOC_FILES = import.meta.glob('../data/docs/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const ACCENT = {
  teal:   { var: 'var(--app-primary)',      rgba: 'rgba(0,194,179,0.4)',  bg: 'rgba(0,194,179,0.1)' },
  amber:  { var: 'var(--app-accent-amber)', rgba: 'rgba(255,180,76,0.4)', bg: 'rgba(255,180,76,0.1)' },
  violet: { var: 'var(--app-accent-2)',     rgba: 'rgba(157,78,221,0.4)', bg: 'rgba(157,78,221,0.1)' },
}

// Lowercase, strip non-alphanumerics, collapse whitespace into hyphens. Used
// for stable in-page anchors generated from H2 headings.
function slugify(text) {
  return String(text)
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
}

// Walk a react-markdown children array and pull out the plain-text content so
// we can slugify a heading regardless of inline formatting (code, em, etc.).
function flattenChildren(children) {
  if (children == null) return ''
  if (typeof children === 'string' || typeof children === 'number') return String(children)
  if (Array.isArray(children)) return children.map(flattenChildren).join('')
  if (children.props && children.props.children) return flattenChildren(children.props.children)
  return ''
}

export default function DocPage() {
  const { slug } = useParams()
  const meta = manifest.docs.find((d) => d.slug === slug)
  const file = DOC_FILES[`../data/docs/${slug}.md`]

  if (!meta || !file) {
    return <Navigate to="/docs" replace />
  }

  const accent = ACCENT[meta.accent] || ACCENT.teal

  // ---- TOC: parse H2 headings out of the raw markdown -------------------
  const toc = useMemo(() => {
    const lines = String(file).split('\n')
    const items = []
    let inFence = false
    for (const line of lines) {
      // Skip code fences so a "## " inside a fenced block doesn't poison the TOC.
      if (line.startsWith('```')) { inFence = !inFence; continue }
      if (inFence) continue
      const m = line.match(/^##\s+(.+?)\s*$/)
      if (m) {
        const text = m[1].replace(/[*_`]/g, '').trim()
        items.push({ text, slug: slugify(text) })
      }
    }
    return items
  }, [file])

  // ---- Scrollspy: highlight the section currently in view ----------------
  const [activeSlug, setActiveSlug] = useState(toc[0]?.slug || '')
  const contentRef = useRef(null)

  useEffect(() => {
    if (!toc.length) return
    const observer = new IntersectionObserver(
      (entries) => {
        // Pick the topmost heading that's currently intersecting.
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) {
          const id = visible[0].target.id
          if (id) setActiveSlug(id)
        }
      },
      {
        // Trigger when the heading is in the top half of the viewport.
        rootMargin: '-80px 0px -55% 0px',
        threshold: 0,
      }
    )
    const headings = (contentRef.current || document).querySelectorAll('h2[id]')
    headings.forEach((h) => observer.observe(h))
    return () => observer.disconnect()
  }, [toc, file])

  // ---- Markdown component overrides --------------------------------------
  const components = useMemo(() => ({
    h2: ({ children }) => {
      const text = flattenChildren(children)
      const id = slugify(text)
      return (
        <h2
          id={id}
          className="text-2xl md:text-[28px] font-semibold tracking-tight mt-12 mb-4 scroll-mt-24"
          style={{ color: 'var(--app-text)' }}
        >
          <span className="font-mono text-sm mr-3 align-middle" style={{ color: accent.var }}>
            {String(toc.findIndex((i) => i.slug === id) + 1).padStart(2, '0')}
          </span>
          {children}
        </h2>
      )
    },
    h1: ({ children }) => (
      <h1 className="text-4xl md:text-5xl font-bold tracking-tight mt-2 mb-3" style={{ color: 'var(--app-text)' }}>
        {children}
      </h1>
    ),
    h3: ({ children }) => (
      <h3 className="text-lg md:text-xl font-semibold mt-8 mb-3" style={{ color: 'var(--app-text)' }}>
        {children}
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="text-base md:text-lg font-semibold mt-6 mb-2" style={{ color: 'var(--app-text)' }}>
        {children}
      </h4>
    ),
    p: ({ children }) => (
      <p className="text-[15px] md:text-base leading-relaxed my-4" style={{ color: 'rgba(255,255,255,0.85)' }}>
        {children}
      </p>
    ),
    ul: ({ children }) => (
      <ul className="my-4 ml-6 space-y-2 list-disc" style={{ color: 'rgba(255,255,255,0.85)' }}>{children}</ul>
    ),
    ol: ({ children }) => (
      <ol className="my-4 ml-6 space-y-2 list-decimal" style={{ color: 'rgba(255,255,255,0.85)' }}>{children}</ol>
    ),
    li: ({ children }) => (
      <li className="text-[15px] md:text-base leading-relaxed">{children}</li>
    ),
    blockquote: ({ children }) => (
      <blockquote
        className="my-5 px-5 py-3 rounded-md italic"
        style={{
          background: 'rgba(255,255,255,0.03)',
          borderLeft: `3px solid ${accent.var}`,
          color: 'rgba(255,255,255,0.78)',
        }}
      >
        {children}
      </blockquote>
    ),
    code: ({ inline, className, children }) => {
      const text = flattenChildren(children)
      if (inline || !className) {
        return (
          <code
            className="font-mono text-[0.92em] px-1.5 py-0.5 rounded"
            style={{
              background: 'rgba(255,255,255,0.06)',
              color: accent.var,
              border: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            {text}
          </code>
        )
      }
      return (
        <code className={className}>{children}</code>
      )
    },
    pre: ({ children }) => (
      <pre
        className="my-5 p-4 rounded-lg overflow-x-auto font-mono text-sm leading-relaxed"
        style={{
          background: 'rgba(0,0,0,0.35)',
          border: '1px solid rgba(255,255,255,0.08)',
          color: 'rgba(255,255,255,0.9)',
        }}
      >
        {children}
      </pre>
    ),
    a: ({ href, children }) => {
      const isInternal = href && (href.startsWith('/') || href.startsWith('#'))
      if (isInternal && href.startsWith('/')) {
        return <Link to={href} style={{ color: accent.var }} className="hover:underline">{children}</Link>
      }
      return (
        <a
          href={href}
          target={isInternal ? undefined : '_blank'}
          rel={isInternal ? undefined : 'noreferrer'}
          style={{ color: accent.var }}
          className="hover:underline"
        >
          {children}
        </a>
      )
    },
    table: ({ children }) => (
      <div className="my-5 overflow-x-auto rounded-lg" style={{ border: '1px solid rgba(255,255,255,0.08)' }}>
        <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>{children}</table>
      </div>
    ),
    thead: ({ children }) => (
      <thead style={{ background: 'rgba(255,255,255,0.04)' }}>{children}</thead>
    ),
    th: ({ children }) => (
      <th
        className="px-4 py-2.5 text-left font-semibold"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', color: 'var(--app-text)' }}
      >
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td
        className="px-4 py-2.5 align-top"
        style={{ borderTop: '1px solid rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.85)' }}
      >
        {children}
      </td>
    ),
    img: ({ src, alt }) => (
      <figure className="my-6">
        <img
          src={src}
          alt={alt || ''}
          className="rounded-lg w-full h-auto"
          style={{ border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.25)' }}
          loading="lazy"
        />
        {alt ? (
          <figcaption className="mt-2 text-xs text-center font-mono" style={{ color: 'var(--muted)' }}>
            {alt}
          </figcaption>
        ) : null}
      </figure>
    ),
    hr: () => (
      <hr className="my-10" style={{ border: 'none', borderTop: '1px solid rgba(255,255,255,0.08)' }} />
    ),
  }), [accent.var, toc])

  return (
    <div className="max-w-7xl mx-auto" style={{ color: 'var(--app-text)' }}>
      {/* DOCS SWITCHER — top breadcrumb pill row */}
      <div
        className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3 px-1 mb-2 font-mono text-[11px] uppercase border-b"
        style={{ borderColor: 'rgba(255,255,255,0.06)', letterSpacing: '0.15em', color: 'var(--muted)' }}
      >
        <span>Docs:</span>
        <Link to="/docs" className="hover:underline" style={{ color: 'var(--app-text)' }}>All Docs</Link>
        {manifest.docs.map((d) => (
          <React.Fragment key={d.slug}>
            <span className="opacity-40">·</span>
            <Link
              to={`/docs/${d.slug}`}
              className="hover:underline"
              style={{ color: d.slug === slug ? (ACCENT[d.accent] || ACCENT.teal).var : 'var(--app-text)' }}
            >
              {d.title}
            </Link>
          </React.Fragment>
        ))}
      </div>

      {/* TWO-COLUMN LAYOUT */}
      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-10 py-8">
        {/* SIDEBAR */}
        <aside className="lg:sticky lg:top-6 self-start">
          <div
            className="rounded-xl p-5"
            style={{
              background: 'linear-gradient(180deg, var(--app-card), rgba(255,255,255,0.01))',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <div
              className="font-mono text-[10px] uppercase mb-1.5"
              style={{ color: accent.var, letterSpacing: '0.18em' }}
            >
              {meta.eyebrow}
            </div>
            <div className="text-base font-semibold leading-snug" style={{ color: 'var(--app-text)' }}>
              {meta.title}
            </div>
            <div className="text-xs mt-1 font-mono" style={{ color: 'var(--muted)' }}>
              ~{meta.readMinutes} min · {toc.length} section{toc.length === 1 ? '' : 's'}
            </div>

            {toc.length > 0 && (
              <nav className="mt-5 -mx-5">
                {toc.map((item, idx) => {
                  const active = item.slug === activeSlug
                  return (
                    <a
                      key={item.slug}
                      href={`#${item.slug}`}
                      className="flex items-baseline gap-3 px-5 py-2 text-sm transition-colors"
                      style={{
                        color: active ? accent.var : 'rgba(255,255,255,0.72)',
                        background: active ? accent.bg : 'transparent',
                        borderLeft: `2px solid ${active ? accent.var : 'transparent'}`,
                      }}
                      onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = 'var(--app-text)' }}
                      onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = 'rgba(255,255,255,0.72)' }}
                    >
                      <span className="font-mono text-[11px] tabular-nums opacity-70" style={{ minWidth: '1.6em' }}>
                        {String(idx + 1).padStart(2, '0')}
                      </span>
                      <span className="leading-snug">{item.text}</span>
                    </a>
                  )
                })}
              </nav>
            )}
          </div>
        </aside>

        {/* MAIN CONTENT */}
        <main ref={contentRef} className="min-w-0">
          <div
            className="font-mono text-[10px] uppercase mb-2"
            style={{ color: accent.var, letterSpacing: '0.2em' }}
          >
            {meta.eyebrow} Documentation
          </div>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
            {file}
          </ReactMarkdown>

          {/* End-of-doc footer w/ link back to hub */}
          <div className="mt-16 pt-8 border-t" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
            <Link
              to="/docs"
              className="inline-flex items-center gap-2 text-sm hover:underline"
              style={{ color: accent.var }}
            >
              ← Back to all docs
            </Link>
          </div>
        </main>
      </div>
    </div>
  )
}
