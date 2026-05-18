/**
 * Compose — creates an empty draft and immediately redirects to its
 * editor page. Per the v0.9 mockup, the user never lands on a separate
 * compose form; clicking "+ New Brief" creates the row and opens it.
 */

import { useEffect, useState } from "react";
import { api, ApiError, DraftDetail } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";

interface Props {
  doctype: string;
}

export function Compose({ doctype }: Props) {
  const { user, loading } = useAuth();
  const [err, setErr] = useState<string | null>(null);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (loading || tried) return;
    if (!user) {
      setErr("login required to compose a draft");
      return;
    }
    if (doctype !== "brief" && doctype !== "feature" && doctype !== "inquisition") {
      setErr(`unknown doctype: ${doctype}`);
      return;
    }
    setTried(true);
    api<DraftDetail>("/drafts", { method: "POST", body: { doctype, civs: [] } })
      .then((d) => {
        showToast("Draft created");
        navigate(`/draft/${d.id}`);
      })
      .catch((e) => {
        const msg = e instanceof ApiError ? String(e.detail) : "create failed";
        setErr(msg);
        showToast(`Compose failed: ${msg}`);
      });
  }, [doctype, user, loading, tried]);

  if (err) {
    return (
      <div className="ta-empty">
        Couldn't start a {doctype}: {err}
        <div style={{ marginTop: 12 }}>
          <a href="#/drafts" className="ta-back-link">← back to drafts</a>
        </div>
      </div>
    );
  }
  return <div className="ta-loading">Creating new {doctype}…</div>;
}
