/** Inquisitions index. */
import { useEffect, useState } from "react";
import { api, InquisitionSummary } from "../api/client";
import { InquisitionCard } from "../components/InquisitionCard";

export function Inquisitions() {
  const [inqs, setInqs] = useState<InquisitionSummary[] | null>(null);
  useEffect(() => {
    api<InquisitionSummary[]>("/inquisitions").then(setInqs).catch(() => setInqs([]));
  }, []);
  return (
    <>
      <div className="ta-civ-index-header">
        <h2 className="ta-civ-index-title">Inquisitions</h2>
        <p className="ta-civ-index-sub">
          {inqs === null ? "Loading…" : `${inqs.length} inquisitions · long-form historical investigations by the Archivists`}
        </p>
      </div>
      <div className="ta-inq-shelf" style={{ borderTop: "1px solid var(--ta-border)" }}>
        {inqs?.map((i) => <InquisitionCard key={i.id} inq={i} />)}
      </div>
    </>
  );
}
