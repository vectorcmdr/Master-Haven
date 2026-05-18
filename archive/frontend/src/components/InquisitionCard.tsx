/** InquisitionCard — gold-accented card with progress bar. */
import { InquisitionSummary } from "../api/client";

export function InquisitionCard({ inq }: { inq: InquisitionSummary }) {
  return (
    <a href={`#/inquisition/${inq.id}`} className="ta-inq-card">
      <div className="ta-inq-numeral">INQUISITION {inq.numeral}</div>
      <h3 className="ta-inq-title">
        {inq.title}
        {inq.subtitle && <span style={{ color: "var(--ta-text-faint)", fontWeight: 400 }}> · {inq.subtitle}</span>}
      </h3>
      <p className="ta-inq-meta">
        By {inq.authors.map((a) => a.name).join(", ") || "—"}
        {" · "}
        {inq.authors.length} historian{inq.authors.length !== 1 ? "s" : ""}
        {" · "}
        {inq.sources_count} source{inq.sources_count !== 1 ? "s" : ""}
        {" · "}
        {inq.state.replace("_", " ")}
      </p>
      {inq.progress < 100 && (
        <div className="ta-inq-progress">
          <span>{inq.progress}%</span>
          <div className="ta-inq-progress-bar">
            <div className="ta-inq-progress-fill" style={{ width: `${inq.progress}%` }} />
          </div>
        </div>
      )}
    </a>
  );
}
