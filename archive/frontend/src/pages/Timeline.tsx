/**
 * Timeline — chronological list (Phase 5a placeholder).
 *
 * The mockup's master timeline is a horizontal-scrub SVG-like layout
 * with one lane per civ + year-axis ticks. That's deferred to Phase
 * 5b (significant DOM/layout work). For 5a we render the same data
 * as a flat reverse-chronological list grouped by year.
 */

import { useEffect, useState } from "react";
import { api, TimelineEntry } from "../api/client";

export function Timeline() {
  const [entries, setEntries] = useState<TimelineEntry[] | null>(null);
  useEffect(() => {
    api<TimelineEntry[]>("/timeline").then(setEntries).catch(() => setEntries([]));
  }, []);

  if (!entries) return <div className="ta-loading">Loading timeline…</div>;

  // Group by year
  const grouped = new Map<number | string, TimelineEntry[]>();
  for (const e of entries) {
    const key = e.year ?? "—";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(e);
  }
  const years = Array.from(grouped.keys()).sort((a, b) => {
    if (typeof a !== "number") return 1;
    if (typeof b !== "number") return -1;
    return b - a;
  });

  return (
    <>
      <div style={{ padding: "22px 16px 14px", borderBottom: "1px solid var(--ta-border)" }}>
        <h1 style={{ fontFamily: "Georgia, serif", fontSize: 28, fontWeight: 500, marginBottom: 6 }}>
          Master timeline
        </h1>
        <p style={{ fontSize: 13, color: "var(--ta-text-dim)" }}>
          Every dated entry across the archive — stories, inquisitions, civ foundings + endings.
        </p>
        <p style={{ fontSize: 11, color: "var(--ta-text-faint)", marginTop: 8, fontStyle: "italic" }}>
          (Phase 5a list view — the lane-per-civ scrubber UI ships in Phase 5b)
        </p>
      </div>

      <div style={{ padding: "16px" }}>
        {years.map((year) => (
          <div key={year} style={{ marginBottom: 24 }}>
            <div style={{
              fontFamily: "Georgia, serif",
              fontSize: 13,
              color: "var(--ta-accent-gold)",
              textTransform: "uppercase",
              letterSpacing: 2,
              marginBottom: 10,
              borderBottom: "1px solid var(--ta-border)",
              paddingBottom: 4,
            }}>{year}</div>
            {grouped.get(year)!.map((e, i) => (
              <a key={`${e.kind}-${e.id ?? e.slug}-${i}`}
                 href={hrefFor(e)}
                 style={{ display: "block", padding: "10px 0", borderBottom: "1px solid var(--ta-border)" }}>
                <div style={{
                  fontSize: 10, color: "var(--ta-text-faint)",
                  textTransform: "uppercase", letterSpacing: 0.8,
                }}>
                  {e.kind} · {fmtDate(e.date)}
                </div>
                <div style={{
                  fontFamily: "Georgia, serif",
                  fontSize: 15, fontWeight: 500, marginTop: 4,
                }}>{e.title}</div>
                {e.civs.length > 0 && (
                  <div style={{ fontSize: 11, color: "var(--ta-text-dim)", marginTop: 4 }}>
                    {e.civs.join(" · ")}
                  </div>
                )}
              </a>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}

function hrefFor(e: TimelineEntry): string {
  switch (e.kind) {
    case "story": return `#/story/${e.id}`;
    case "inquisition": return `#/inquisition/${e.id}`;
    case "civ-founded":
    case "civ-ended":
      return e.slug ? `#/civ/${e.slug}` : "#";
    default:
      return "#";
  }
}

function fmtDate(d: string): string {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return d;
  }
}
