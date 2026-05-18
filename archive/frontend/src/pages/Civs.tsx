/** Civilizations index grid. */
import { useEffect, useState } from "react";
import { api, CivilizationSummary } from "../api/client";
import { CivCard } from "../components/CivCard";

export function Civs() {
  const [civs, setCivs] = useState<CivilizationSummary[] | null>(null);
  useEffect(() => {
    // Request a large page so all civs land on one screen. With 172
    // partner rows today and room to grow, 500 is comfortable; the
    // backend caps at 500 to bound memory.
    api<CivilizationSummary[]>("/civilizations", { query: { page_size: 500 } })
      .then(setCivs)
      .catch(() => setCivs([]));
  }, []);
  return (
    <>
      <div className="ta-civ-index-header">
        <h2 className="ta-civ-index-title">Civilizations</h2>
        <p className="ta-civ-index-sub">
          {civs === null ? "Loading…" : `${civs.length} civs documented · all sizes, all states · same structural treatment`}
        </p>
      </div>
      <div className="ta-civ-grid">
        {civs?.map((c) => <CivCard key={c.slug} civ={c} />)}
      </div>
    </>
  );
}
