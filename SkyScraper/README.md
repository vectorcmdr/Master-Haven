# Project Skyscraper — community tracker

A single-page tracker for the **Project Skyscraper** No Man's Sky ARG, compiled in
support of the [ETARC investigation thread](https://forums.atlas-65.com/t/project-skyscraper-no-mans-sky-arg/9095).
Live at **skyscraper.havenmap.online**.

This is a documentation site, not an investigation hub — every finding is first
surfaced on ETARC and credited back to the person who found it.

## Layout

```
SkyScraper/
├── index.html          The content — markup only; what a contributor edits
├── styles.css          All styling, linked from <head>
├── app.js              Tab switching, timeline expand, puzzle filter — linked before </body>
├── README.md           This file
└── watch/              Change-notifier that polls the ARG and posts Discord/forum alerts
    ├── skyscraper_watch.py
    └── config.env.example   Copy to config.env and fill in (config.env is gitignored)
```

The site is three plain static files — **no build step, no bundler, no
dependencies**. `index.html` links `styles.css` and `app.js` directly; all three
sit in the same folder. Fonts load from Google Fonts over CDN. To preview, open
`index.html` in a browser or serve the folder (`python -m http.server`).

Day-to-day you only touch **`index.html`** — that's where every finding lives.
Styling is in `styles.css`, behavior in `app.js`; you rarely need either.

The page has no embedded images by design — it's a text/forensic writeup. ARG
artefacts are referenced by filename in prose, not displayed.

The page has no embedded images by design — it's a text/forensic writeup. ARG
artefacts are referenced by filename in prose, not displayed.

## How `index.html` is organized

A hero + stats strip + a 7-tab interface. Each tab is a `<section class="panel">`
whose `id` matches a nav button's `data-tab`:

| Tab | `id` | What lives here |
|-----|------|-----------------|
| 01 NOW | `tab-now` | The lead. Latest event, "how we got here", what we're watching, live puzzles |
| 02 NEW HERE? | `tab-new` | 60-second catch-up for newcomers |
| 03 TIMELINE | `tab-timeline` | Every event in order, grouped by phase; click a day to expand |
| 04 PUZZLES | `tab-puzzles` | Each puzzle stated, with an active/solved filter |
| 05 THE ARCHITECT | `tab-architect` | Profile of the ARG's author |
| 06 CHANNELS | `tab-channels` | Every surface the Architect operates on |
| 07 CREDITS | `tab-credits` | One card per investigator |

Section dividers (`<!-- TAB N · NAME -->` in HTML, `/* ==== SECTION ==== */` in
CSS) mark each region — search those to jump around.

`app.js` does three things: tab switching (with `#hash` deep-links),
click-to-expand on timeline entries that have a `.tl-deep` block, and the
Puzzles active/solved filter (counts are derived automatically from how many
puzzles carry `status-solved`).

## Editing conventions

**Always credit the source.** Inline credit uses a quiet italic span at the end
of the sentence or list item:

```html
<span class="by">DevilinPixy · ETARC thread 9539</span>
```

**Status mechanic.** The ARG flags live puzzles `unstable`/`unverified` and flips
them to `stable` once solved. Mirror that with the puzzle status pill — and keep
it accurate, because the Puzzles filter counts depend on it:

```html
<div class="puzzle-status status-active">active</div>
<!-- status-open · status-partial · status-active · status-solved -->
```

**Stats strip** (top of the page) is hand-maintained — update the numbers when
they change: memory blocs `0 / 365`, site posts, anomalies, channels, gate
password, reality status.

**Dual time.** The ARG keeps Excel serial dates in slugs and Unix epochs in
"memory bloc" IDs; the page reports event times in **UTC+1** (the Architect's
timezone). Keep that consistent.

### Block patterns to copy

A **timeline entry** (under a `<h3>` phase heading), deep-dive optional:

```html
<div class="timeline-entry">
  <div class="timeline-date"><span class="te-y">2026</span>Mar 03 · 20:14</div>
  <div class="timeline-body">
    <div class="te-t">Short headline</div>
    Body text with <code>inline codes</code> and <strong>emphasis</strong>.
    <div class="tl-deep">
      <span class="tl-deep-label">Deep dive</span>
      <ul>
        <li>Detail. <span class="by">credit</span></li>
      </ul>
    </div>
  </div>
</div>
```

A **watch card** (NOW tab, "what we're watching for next"):

```html
<div class="watch-card">
  <div class="wc-label">mechanic · active now</div>
  <div class="wc-title">Short title</div>
  <div class="wc-d">What it is and why it matters. <span class="by">credit</span></div>
</div>
```

A **puzzle** (Puzzles tab):

```html
<div class="puzzle">
  <div class="puzzle-header">
    <div class="puzzle-name">Puzzle name</div>
    <div class="puzzle-status status-active">active</div>
  </div>
  <div class="puzzle-body">
    <div class="puzzle-prompt">The setup. <span class="by">credit</span></div>
    <div class="puzzle-section">
      <div class="puzzle-section-label">What's been tried</div>
      <ul><li>…</li></ul>
    </div>
  </div>
</div>
```

A **channel card** (Channels tab):

```html
<div class="ch-card">
  <div class="ch-icon">●</div>
  <div class="ch-name">Surface name</div>
  <div class="ch-url"><a href="…" target="_blank" rel="noopener">display url</a></div>
  <div class="ch-meta">What it is. <span class="by">credit</span></div>
</div>
```

An **investigator card** (Credits tab):

```html
<div class="investigator-card">
  <div class="inv-name">handle<span class="inv-handle">ETARC · pp. 9, 11</span></div>
  <div class="inv-body"><strong>What they found.</strong> Detail.</div>
</div>
```

All external links use `target="_blank" rel="noopener"`.

## The watcher (`watch/`)

`skyscraper_watch.py` polls the ARG's public surfaces (WordPress REST, sitemaps,
the TR4CE image bytes, Bluesky, the reserved second site), diffs against the last
snapshot, and posts a Discord webhook — optionally mirrored to the ETARC thread.
Pure stdlib, runs on the Pi via cron. It is independent of the tracker page;
editing `index.html` doesn't affect it. Its own docstring covers the run modes
(`--seed`, `--test`, `--authorize`). Secrets and runtime state (`config.env`,
`state.json`, `discourse_priv.pem`, `watch.log`) are gitignored.

## Deploy

Served by an nginx container (`skyscraper-static`) on the Pi — no image build,
no frontend compile. The deploy is just shipping the static files and refreshing
the mount.

> **Mount note:** now that the site is three files (`index.html`, `styles.css`,
> `app.js`), nginx must serve the **whole folder**, not a single file. If the Pi
> compose bind-mounts `index.html` on its own
> (`./index.html:/usr/share/nginx/html/index.html`), switch it to mount the
> directory (`./:/usr/share/nginx/html:ro`) so `styles.css` and `app.js` resolve
> — otherwise the page loads unstyled and the tabs won't switch.

The watcher runs separately on a `*/15` cron from `~/docker/skyscraper-watch/`.
