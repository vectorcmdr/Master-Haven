/** CivCard — civilization card with stat strip + colored band. */
import { CivilizationSummary } from "../api/client";

export function CivCard({ civ }: { civ: CivilizationSummary }) {
  const styles = {
    "--c1": civ.color_primary,
    "--c2": civ.color_secondary,
  } as React.CSSProperties;
  return (
    <a href={`#/civ/${civ.slug}`} className="ta-civ-card" style={styles}>
      <div className="ta-civ-card-band" />
      <div className="ta-civ-card-body">
        <div className="ta-civ-card-name">
          {civ.name}
          <span className={`ta-civ-card-status ta-status-${civ.status}`}>
            {civ.status}
          </span>
        </div>
        <div className="ta-civ-card-meta">
          {civ.galaxy} · founded {civ.founded}
          {civ.ended ? ` – ${civ.ended}` : ""} · {civ.tagline}
        </div>
        <div className="ta-civ-card-stats">
          <span><b>{civ.stats.entries}</b> entries</span>
          <span><b>{civ.stats.inquisitions}</b> inq.</span>
          <span><b>{civ.stats.people}</b> people</span>
        </div>
      </div>
    </a>
  );
}
