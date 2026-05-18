/**
 * useAuth — reads /auth/me, exposes the current user.
 *
 * Centralized so any component can show user-aware UI without each
 * one re-fetching. Auto-refetches on window focus.
 *
 * Returns:
 *   user      MeUser | null (null = not logged in)
 *   loading   true on first load
 *   refresh   re-fetch /auth/me (call after login/logout)
 */

import { useCallback, useEffect, useState } from "react";
import { apiRaw, ApiError, MeUser } from "../api/client";

let cachedUser: MeUser | null | undefined = undefined;
const listeners = new Set<(u: MeUser | null) => void>();

function notify(u: MeUser | null) {
  cachedUser = u;
  listeners.forEach((fn) => fn(u));
}

async function fetchMe(): Promise<MeUser | null> {
  try {
    const env = await apiRaw<MeUser>("/auth/me");
    return env?.data ?? null;
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }
}

export function useAuth() {
  const [user, setUser] = useState<MeUser | null>(cachedUser ?? null);
  const [loading, setLoading] = useState<boolean>(cachedUser === undefined);

  const refresh = useCallback(async () => {
    setLoading(true);
    const u = await fetchMe();
    notify(u);
    setLoading(false);
  }, []);

  useEffect(() => {
    const onChange = (u: MeUser | null) => setUser(u);
    listeners.add(onChange);
    if (cachedUser === undefined) refresh();
    return () => {
      listeners.delete(onChange);
    };
  }, [refresh]);

  return { user, loading, refresh };
}

/** Imperative helpers for outside components (login flows). */
export async function refreshAuth(): Promise<MeUser | null> {
  const u = await fetchMe();
  notify(u);
  return u;
}

export function logoutClient() {
  notify(null);
}
