/** DraftRow — list row for /drafts. */
import { DraftSummary } from "../api/client";
import { DocTypeTag } from "./Tag";
import { StatusPill } from "./StatusPill";

export function DraftRow({ draft }: { draft: DraftSummary }) {
  const allAuthors = [draft.author.name, ...draft.coauthors.map((c) => c.name)];
  return (
    <a href={`#/draft/${draft.id}`} className="ta-draft-row">
      <div className="ta-draft-row-top">
        <DocTypeTag doctype={draft.doctype} />
        <StatusPill status={draft.status} />
        {draft.doctype === "inquisition" && draft.numeral && (
          <span style={{ fontSize: 11, color: "var(--ta-text-faint)" }}>{draft.numeral}</span>
        )}
      </div>
      <h3 className={`ta-draft-headline${!draft.headline ? " ta-draft-headline-untitled" : ""}`}>
        {draft.headline || "Untitled draft"}
      </h3>
      <div className="ta-draft-meta">
        <span>By <b>{allAuthors.join(" + ")}</b></span>
        <span>{relativeTime(draft.last_edited_at)}</span>
        {draft.civs.length > 0 && <span>{draft.civs.join(" · ")}</span>}
      </div>
    </a>
  );
}

/** Cheap relative-time formatter for last-edited timestamps. */
function relativeTime(iso: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (!then) return iso;
  const diffMs = Date.now() - then;
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.floor(hr / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}
