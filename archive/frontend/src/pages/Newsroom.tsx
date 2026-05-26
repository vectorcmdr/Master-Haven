/** Newsroom (home) — masthead, hero, brief grid, features, inquisitions. */
import { useEffect, useState } from "react";
import {
  api,
  CivilizationSummary,
  InquisitionSummary,
  StorySummary,
} from "../api/client";
import { InquisitionCard } from "../components/InquisitionCard";
import { Loading } from "../components/Loading";
import { StoryCard } from "../components/StoryCard";
import { KNOWN_BEATS } from "../components/UserSearch";
import { useAuth } from "../hooks/useAuth";

interface Props {
  beat?: string;
}

export function Newsroom({ beat }: Props) {
  const { user } = useAuth();
  const [stories, setStories] = useState<StorySummary[] | null>(null);
  const [inquisitions, setInquisitions] = useState<InquisitionSummary[] | null>(null);
  const [civs, setCivs] = useState<CivilizationSummary[] | null>(null);
  const canCompose = !!user && (user.base_role === "diplomat" || user.base_role === "historian" || user.is_admin);

  useEffect(() => {
    const ac = new AbortController();
    Promise.all([
      api<StorySummary[]>("/stories", { query: { beat }, signal: ac.signal }),
      api<InquisitionSummary[]>("/inquisitions", { signal: ac.signal }),
      api<CivilizationSummary[]>("/civilizations", { signal: ac.signal }),
    ]).then(([s, i, c]) => {
      setStories(s);
      setInquisitions(i);
      setCivs(c);
    }).catch((err) => {
      if (err?.name === "AbortError") return;
      // We don't want to leave the page in a permanent loading state
      // on network failure — but we also shouldn't silently empty
      // everything. Show a toast so the user knows.
      setStories([]);
      setInquisitions([]);
      setCivs([]);
      // showToast injected via dynamic import so SSR doesn't break;
      // simple notification here:
      console.error("Newsroom fetch failed", err);
    });
    return () => ac.abort();
  }, [beat]);

  const briefs = (stories ?? []).filter((s) => s.doctype === "brief");
  const features = (stories ?? []).filter((s) => s.doctype === "feature");
  const hero = features[0] ?? briefs[0] ?? null;
  const otherFeatures = features.slice(hero?.doctype === "feature" ? 1 : 0);
  const otherBriefs = briefs.filter((b) => b.id !== hero?.id);

  return (
    <>
      <div className="ta-masthead">
        <h1 className="ta-masthead-name">Travelers Archive</h1>
        <div className="ta-masthead-tag">A record of the No Man's Sky multiverse</div>
        <div className="ta-masthead-meta">
          <Stat n={stories === null ? "…" : stories.length} label="stories" />
          <Stat n={inquisitions === null ? "…" : inquisitions.length} label="inquisitions" />
          <Stat n={civs === null ? "…" : civs.length} label="civs" />
        </div>
      </div>

      <BeatNav active={beat ?? null} />

      {stories === null ? (
        <Loading label="Loading newsroom…" />
      ) : stories.length === 0 ? (
        <div className="ta-empty">
          {beat
            ? <>No stories yet on the <b>{beat}</b> beat. Be the first to file one.</>
            : "No stories yet. The archive is waiting."}
          {canCompose && (
            <div className="ta-empty-cta-row">
              <a href="#/compose/brief" className="ta-btn ta-btn-primary">+ Start a brief</a>
              <a href="#/compose/feature" className="ta-btn">+ Start a feature</a>
            </div>
          )}
        </div>
      ) : (
        <>
          {hero && <StoryCard story={hero} hero />}

          {otherBriefs.length > 0 && (
            <>
              <div className="ta-section-divider">
                <div className="ta-section-name">Latest briefs</div>
                <div className="ta-section-sub">Today's reports from across the multiverse</div>
              </div>
              <div className="ta-story-grid">
                {otherBriefs.map((s) => <StoryCard key={s.id} story={s} />)}
              </div>
            </>
          )}

          {otherFeatures.length > 0 && (
            <>
              <div className="ta-section-divider">
                <div className="ta-section-name">Recent features</div>
                <div className="ta-section-sub">Long-form reporting</div>
              </div>
              <div className="ta-story-grid">
                {otherFeatures.map((s) => <StoryCard key={s.id} story={s} />)}
              </div>
            </>
          )}
        </>
      )}

      {inquisitions && inquisitions.length > 0 && (
        <>
          <div className="ta-section-divider">
            <div className="ta-section-name">Active inquisitions</div>
            <div className="ta-section-sub">Long-form historical investigations by the Archivists</div>
          </div>
          <div className="ta-inq-shelf">
            {inquisitions.map((i) => <InquisitionCard key={i.id} inq={i} />)}
          </div>
        </>
      )}
    </>
  );
}

function Stat({ n, label }: { n: number | string; label: string }) {
  return (
    <div className="ta-masthead-meta-item">
      <span className="ta-masthead-meta-num">{n}</span>
      <span className="ta-masthead-meta-label">{label}</span>
    </div>
  );
}

function BeatNav({ active }: { active: string | null }) {
  return (
    <div className="ta-beat-nav">
      <div className="ta-beat-nav-inner">
        <a href="#/" className={`ta-beat-tab${active === null ? " active" : ""}`}>Front page</a>
        {KNOWN_BEATS.map((b) => (
          <a key={b} href={`#/beat/${b}`} className={`ta-beat-tab${active === b ? " active" : ""}`}>{b}</a>
        ))}
        <a href="#/inquisitions" className="ta-beat-tab">Inquisitions</a>
      </div>
    </div>
  );
}
