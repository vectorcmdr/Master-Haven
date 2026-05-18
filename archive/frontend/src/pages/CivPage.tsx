/** Civilization detail page — hero + stat strip + coverage list. */
import { useEffect, useState } from "react";
import { api, CivilizationDetail, CoverageItem } from "../api/client";

export function CivPage({ slug }: { slug: string }) {
  const [civ, setCiv] = useState<CivilizationDetail | null>(null);
  const [coverage, setCoverage] = useState<CoverageItem[]>([]);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setCiv(null);
    setCoverage([]);
    setNotFound(false);
    Promise.all([
      api<CivilizationDetail>(`/civilizations/${slug}`),
      api<CoverageItem[]>(`/civilizations/${slug}/coverage`),
    ])
      .then(([c, cov]) => {
        setCiv(c);
        setCoverage(cov);
      })
      .catch(() => setNotFound(true));
  }, [slug]);

  if (notFound) return <div className="ta-empty">Civilization not found.</div>;
  if (!civ) return <div className="ta-loading">Loading civilization…</div>;

  const heroStyles = {
    "--c1": civ.color_primary,
    "--c2": civ.color_secondary,
  } as React.CSSProperties;

  return (
    <>
      <div className="ta-civ-hero" style={heroStyles}>
        <div className="ta-civ-hero-eyebrow">Civilization</div>
        <h1 className="ta-civ-hero-name">{civ.name}</h1>
        <div className="ta-civ-hero-tagline">
          {civ.galaxy} galaxy · founded {civ.founded}
          {civ.ended ? ` – ${civ.ended}` : ""} · {civ.tagline}
        </div>
      </div>

      <div className="ta-civ-stats-strip">
        <CivStat n={civ.stats.entries} label="Entries" />
        <CivStat n={civ.stats.inquisitions} label="Inquisitions" />
        <CivStat n={civ.stats.people} label="People" />
        <CivStat n={civ.stats.years} label="Years" />
      </div>

      <div className="ta-civ-body">
        <div className="ta-civ-body-eyebrow">
          All coverage tagged {civ.name} · {coverage.length} entries
        </div>

        {civ.description && (
          <p style={{
            fontFamily: "Georgia, serif", fontSize: 15, lineHeight: 1.6,
            color: "var(--ta-text-dim)", marginBottom: 18,
          }}>
            {civ.description}
          </p>
        )}

        {coverage.length === 0 ? (
          <p style={{ color: "var(--ta-text-faint)", fontSize: 13 }}>
            No coverage yet. {civ.name} is documented but has no published stories.
          </p>
        ) : (
          <div className="ta-coverage-list">
            {coverage.map((c) => <CoverageRow key={`${c.kind}-${c.id}`} item={c} />)}
          </div>
        )}
      </div>
    </>
  );
}

function CivStat({ n, label }: { n: number; label: string }) {
  return (
    <div className="ta-civ-stat">
      <div className="ta-civ-stat-num">{n}</div>
      <div className="ta-civ-stat-label">{label}</div>
    </div>
  );
}

function CoverageRow({ item }: { item: CoverageItem }) {
  const href = item.kind === "story" ? `#/story/${item.id}` : `#/inquisition/${item.id}`;
  const dateStr = item.published_at || item.started_at || "";
  const niceDate = dateStr
    ? new Date(dateStr).toLocaleDateString("en-US", { dateStyle: "medium" })
    : "";
  return (
    <a href={href} className="ta-coverage-item">
      <div className="ta-coverage-date">
        {niceDate} · {item.kind} · {item.beat || item.state || ""}
      </div>
      <h3 className="ta-coverage-title">{item.headline}</h3>
      {item.deck && <p className="ta-coverage-deck">{item.deck}</p>}
      {item.author && (
        <div className="ta-byline-row"><span>By <b>{item.author.name}</b></span></div>
      )}
    </a>
  );
}
