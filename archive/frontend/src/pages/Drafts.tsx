/** Drafts list with personal/team toggle. */
import { useEffect, useState } from "react";
import { api, DraftSummary } from "../api/client";
import { DraftRow } from "../components/DraftRow";
import { useAuth } from "../hooks/useAuth";

type View = "personal" | "team";

export function Drafts() {
  const { user, loading } = useAuth();
  const [view, setView] = useState<View>("personal");
  const [drafts, setDrafts] = useState<DraftSummary[] | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      setDrafts([]);
      return;
    }
    setDrafts(null);
    api<DraftSummary[]>("/drafts", { query: { view } })
      .then(setDrafts)
      .catch(() => setDrafts([]));
  }, [view, user, loading]);

  if (loading) return <div className="ta-loading">Loading…</div>;
  if (!user) {
    return (
      <div className="ta-empty">
        Log in via the dev panel to see drafts.
      </div>
    );
  }

  return (
    <div className="ta-drafts-page">
      <h1 className="ta-drafts-title">Drafts</h1>
      <p className="ta-drafts-sub">Work in progress. Visible to the team. Not yet published.</p>

      <div className="ta-drafts-toggle">
        <button
          className={`ta-drafts-toggle-btn${view === "personal" ? " active" : ""}`}
          onClick={() => setView("personal")}
        >Personal</button>
        <button
          className={`ta-drafts-toggle-btn${view === "team" ? " active" : ""}`}
          onClick={() => setView("team")}
        >Team</button>
      </div>

      <div className="ta-drafts-count">
        {drafts === null ? "loading…" : `${drafts.length} ${drafts.length === 1 ? "draft" : "drafts"}`}
        {view === "personal" ? " where you're the author or a co-author" : " across the team"}
      </div>

      {drafts === null ? (
        <div className="ta-loading">…</div>
      ) : drafts.length === 0 ? (
        <div className="ta-empty">
          {view === "personal"
            ? "No personal drafts yet. Start a new brief, feature, or inquisition from the dashboard."
            : "No team drafts in progress right now."}
        </div>
      ) : (
        <div>{drafts.map((d) => <DraftRow key={d.id} draft={d} />)}</div>
      )}
    </div>
  );
}
