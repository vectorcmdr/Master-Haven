/**
 * Draft editor + reviewer view.
 *
 * - Authors / co-authors get editable headline+deck+body with 800ms
 *   debounced auto-save (PATCH /drafts/{id})
 * - Anyone with a team role can read + comment
 * - Editors see Return / Mark Ready buttons when status=in_review
 * - Authors see Submit (draft/returned) and Publish (ready) buttons
 *
 * Phase 5a defers: inline comment quote attachment via DOM Selection.
 * Comments here are document-level (no quoted_text). The backend
 * supports both — Phase 5b wires the selection UI.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  apiRaw,
  ApiError,
  CommentDetail,
  DraftDetail,
} from "../api/client";
import { Avatar } from "../components/Avatar";
import { StatusPill } from "../components/StatusPill";
import { useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";
import { navigate } from "../router";

interface Props {
  id: string;
}

export function Draft({ id }: Props) {
  const { user } = useAuth();
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [comments, setComments] = useState<CommentDetail[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [savedAt, setSavedAt] = useState<string>("");
  const [commentBody, setCommentBody] = useState("");
  const saveTimer = useRef<number | null>(null);

  const reload = useCallback(async () => {
    try {
      const d = await api<DraftDetail>(`/drafts/${id}`);
      setDraft(d);
      const c = await api<CommentDetail[]>(`/drafts/${id}/comments`);
      setComments(c);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 401 || e.status === 403)) {
        setNotFound(true);
      }
    }
  }, [id]);

  useEffect(() => { reload(); }, [reload]);

  if (notFound) return <div className="ta-empty">Draft not found, or you don't have access.</div>;
  if (!user) return <div className="ta-empty">Log in to view drafts.</div>;
  if (!draft) return <div className="ta-loading">Loading draft…</div>;

  const isAuthor = draft.author.id === user.id;
  const isCoauthor = draft.coauthors.some((c) => c.user_id === user.id);
  const canEdit = isAuthor || isCoauthor;
  const isEditor = user.is_editor || user.is_admin;
  const isPublished = draft.status === "published";

  // Auto-save on field change (800ms debounce)
  const scheduleSave = (patch: Record<string, unknown>) => {
    if (!canEdit || isPublished) return;
    if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(async () => {
      try {
        const updated = await api<DraftDetail>(`/drafts/${id}`, { method: "PATCH", body: patch });
        setDraft(updated);
        setSavedAt("just now");
      } catch {
        showToast("Auto-save failed");
      }
    }, 800);
  };

  const transition = async (path: string, label: string) => {
    try {
      const updated = await apiRaw<DraftDetail>(`/drafts/${id}/${path}`, { method: "POST" });
      if (updated?.data) setDraft(updated.data);
      showToast(label);
      // On publish, send the user to the new story/inquisition
      if (path === "publish" && updated?.data) {
        if (updated.data.published_as_story_id) {
          navigate(`/story/${updated.data.published_as_story_id}`);
        } else if (updated.data.published_as_inquisition_id) {
          navigate(`/inquisition/${updated.data.published_as_inquisition_id}`);
        }
      }
    } catch (e) {
      if (e instanceof ApiError) showToast(`${label} failed: ${e.detail}`);
      else showToast(`${label} failed`);
    }
  };

  const postComment = async () => {
    const body = commentBody.trim();
    if (!body) return;
    try {
      const env = await apiRaw<CommentDetail>(
        `/drafts/${id}/comments`,
        { method: "POST", body: { body } },
      );
      if (env?.data) setComments((prev) => [...prev, env.data]);
      setCommentBody("");
      showToast("Comment posted");
    } catch {
      showToast("Comment failed");
    }
  };

  return (
    <div className="ta-draft-page">
      <a href="#/drafts" className="ta-back-link">← Back to drafts</a>

      {!canEdit && (
        <div style={{
          background: "var(--ta-surface)",
          borderLeft: "3px solid var(--ta-accent-blue)",
          padding: "10px 14px",
          borderRadius: "0 6px 6px 0",
          fontSize: 12, color: "var(--ta-text-dim)",
          marginBottom: 14, lineHeight: 1.45,
        }}>
          <b>Read-only.</b> You're viewing as a team member. You can leave
          comments. Edit access is held by {draft.author.name}
          {draft.coauthors.length > 0 ? " and co-authors" : ""}.
        </div>
      )}

      <div className="ta-draft-status-strip">
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <StatusPill status={draft.status} />
          {canEdit && savedAt && (
            <span className="ta-draft-saved">Saved {savedAt}</span>
          )}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {canEdit && (draft.status === "draft" || draft.status === "returned") && (
            <button className="ta-btn" onClick={() => transition("submit", "Submitted for review")}>
              {draft.status === "returned" ? "Resubmit" : "Submit for review"}
            </button>
          )}
          {isEditor && draft.status === "in_review" && (
            <>
              <button className="ta-btn ta-btn-warn" onClick={() => transition("return", "Returned to author")}>
                Return with notes
              </button>
              <button className="ta-btn ta-btn-primary" onClick={() => transition("mark_ready", "Marked ready")}>
                Mark ready
              </button>
            </>
          )}
          {canEdit && draft.status === "ready" && (
            <button className="ta-btn ta-btn-publish" onClick={() => transition("publish", "Published")}>
              Publish now
            </button>
          )}
        </div>
      </div>

      <div className="ta-story-tags" style={{ margin: "0 0 12px" }}>
        <span className={`ta-doctype ta-doctype-${draft.doctype}`}>{draft.doctype}</span>
        {draft.numeral && (
          <span style={{ fontSize: 11, color: "var(--ta-text-faint)", marginLeft: 8 }}>
            Inquisition {draft.numeral}
          </span>
        )}
      </div>

      {canEdit ? (
        <>
          <input
            className="ta-draft-editor-headline"
            placeholder="Headline"
            defaultValue={draft.headline ?? ""}
            onChange={(e) => scheduleSave({ headline: e.target.value })}
          />
          <input
            className="ta-draft-editor-deck"
            placeholder="Deck (subtitle)"
            defaultValue={draft.deck ?? ""}
            onChange={(e) => scheduleSave({ deck: e.target.value })}
          />
          <textarea
            className="ta-draft-editor-body"
            placeholder="Body…"
            defaultValue={draft.body ?? ""}
            onChange={(e) => scheduleSave({ body: e.target.value })}
          />
        </>
      ) : (
        <>
          <h1 style={{
            fontFamily: "Georgia, serif", fontSize: 22, fontWeight: 500,
            lineHeight: 1.25, marginBottom: 8,
          }}>
            {draft.headline || <span style={{ color: "var(--ta-text-faint)", fontStyle: "italic" }}>Untitled draft</span>}
          </h1>
          {draft.deck && (
            <p style={{
              fontFamily: "Georgia, serif", fontStyle: "italic",
              color: "var(--ta-text-dim)", marginBottom: 12,
            }}>{draft.deck}</p>
          )}
          <div style={{
            fontFamily: "Georgia, serif", fontSize: 16, lineHeight: 1.65,
            color: "var(--ta-text)", whiteSpace: "pre-wrap", padding: "8px 0",
          }}>
            {draft.body}
          </div>
        </>
      )}

      <div className="ta-draft-authors">
        <div className="ta-draft-authors-label">Author + co-authors</div>
        <div className="ta-draft-authors-list">
          <a href={`#/profile/${draft.author.slug}`} className="ta-draft-author-chip ta-draft-author-chip-primary">
            <Avatar author={draft.author} />
            <span>{draft.author.name}</span>
          </a>
          {draft.coauthors.map((c) => (
            <a key={c.user_id} href={`#/profile/${c.slug}`} className="ta-draft-author-chip">
              <Avatar author={c} />
              <span>{c.name}</span>
            </a>
          ))}
        </div>
      </div>

      <div className="ta-draft-comments">
        <div className="ta-draft-comments-title">Comments ({comments.length})</div>
        {comments.length === 0 ? (
          <div style={{ padding: "14px 0", color: "var(--ta-text-faint)", fontSize: 13, fontStyle: "italic" }}>
            No comments yet. Be the first to leave one.
          </div>
        ) : (
          comments.map((c) => (
            <div key={c.id} className="ta-draft-comment">
              <div className="ta-draft-comment-head">
                <Avatar author={c.author} />
                <span className="ta-draft-comment-author">{c.author.name}</span>
                <span className="ta-draft-comment-time">{new Date(c.created_at).toLocaleString()}</span>
              </div>
              {c.quoted_text && (
                <div className="ta-draft-comment-quote">"{c.quoted_text}"</div>
              )}
              <div className="ta-draft-comment-text">{c.body}</div>
            </div>
          ))
        )}

        <div className="ta-draft-comment-form">
          <div style={{
            fontSize: 11, color: "var(--ta-text-faint)",
            textTransform: "uppercase", letterSpacing: 0.6,
            marginBottom: 6, fontWeight: 500,
          }}>
            Leave a comment
          </div>
          <textarea
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
            placeholder="Add a note. Use @username to ping someone. Inline quoting ships in 5b."
          />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
            <button className="ta-btn ta-btn-primary" onClick={postComment}>Post comment</button>
            <span style={{ fontSize: 11, color: "var(--ta-text-faint)" }}>
              Visible to all team members
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
