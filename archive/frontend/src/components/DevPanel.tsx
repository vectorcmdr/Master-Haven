/**
 * DevPanel — role switcher (dev mode only).
 *
 * Fetches /api/v1/auth/dev/users on first open, lets you pick one,
 * POSTs /auth/dev/login, then refreshes the auth context.
 *
 * In production the dev endpoints return 404 — this panel just shows
 * a "dev mode unavailable" message and is otherwise inert. The label
 * collapsed to "Logged in as X" is always rendered so the persona
 * is visible in the corner during testing.
 */

import { useEffect, useState } from "react";
import { apiRaw, ApiError, DevUser } from "../api/client";
import { refreshAuth, useAuth } from "../hooks/useAuth";
import { showToast } from "../hooks/useToast";

export function DevPanel() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [devUsers, setDevUsers] = useState<DevUser[]>([]);
  const [devAvailable, setDevAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    if (!open) return;
    if (devAvailable !== null) return;
    apiRaw<DevUser[]>("/auth/dev/users")
      .then((env) => {
        setDevUsers(env?.data ?? []);
        setDevAvailable(true);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) {
          setDevAvailable(false);
        } else {
          showToast("Dev panel failed to load");
        }
      });
  }, [open, devAvailable]);

  const loginAs = async (id: number) => {
    try {
      await apiRaw("/auth/dev/login", { method: "POST", body: { user_id: id } });
      await refreshAuth();
      showToast("Logged in");
    } catch {
      showToast("Login failed");
    }
  };

  const logout = async () => {
    try {
      await apiRaw("/auth/logout", { method: "POST" });
      await refreshAuth();
      showToast("Logged out");
    } catch {
      showToast("Logout failed");
    }
  };

  const label = user
    ? `${user.display_name} · ${user.is_admin ? "admin" : user.is_editor ? user.base_role + " (editor)" : user.base_role}`
    : "Not logged in";

  if (!open) {
    return (
      <button
        className="ta-dev-panel"
        onClick={() => setOpen(true)}
        title="Dev panel"
      >
        <span style={{
          display: "inline-block", width: 8, height: 8, borderRadius: "50%",
          background: user ? "#97C459" : "#888",
        }} />
        {label}
      </button>
    );
  }

  return (
    <div className="ta-dev-panel-expanded open">
      <button
        className="ta-dev-panel-close"
        onClick={() => setOpen(false)}
        aria-label="Close"
      >×</button>

      <div className="ta-dev-panel-label">Current</div>
      <div style={{ marginBottom: 12, fontSize: 12 }}>{label}</div>

      {devAvailable === false && (
        <div style={{ fontSize: 11, color: "var(--ta-text-faint)" }}>
          Dev login not available — backend is in production mode.
        </div>
      )}

      {devAvailable && (
        <>
          <div className="ta-dev-panel-label">Switch persona</div>
          <div className="ta-dev-panel-row">
            {devUsers.map((u) => (
              <button
                key={u.id}
                className={`ta-dev-panel-btn${user?.id === u.id ? " active" : ""}`}
                onClick={() => loginAs(u.id)}
                title={`${u.base_role}${u.is_editor ? " · editor" : ""}${u.is_admin ? " · admin" : ""}`}
              >
                {u.name}
                {u.is_admin ? " ★" : u.is_editor ? " ✎" : ""}
              </button>
            ))}
          </div>
          <button
            className="ta-dev-panel-btn"
            onClick={logout}
            style={{ marginTop: 4 }}
          >Log out</button>
          <div style={{ fontSize: 10, color: "var(--ta-text-faint)", marginTop: 10, lineHeight: 1.4 }}>
            ★ admin · ✎ editor · plain = diplomat/historian by base role
          </div>
        </>
      )}
    </div>
  );
}
