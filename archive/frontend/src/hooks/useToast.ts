/**
 * useToast — singleton toast bus.
 *
 * Components call showToast("...") to flash a message. The <Toast/>
 * component subscribes and renders it. ~2.5s default duration.
 */

import { useEffect, useState } from "react";

type Listener = (msg: string | null) => void;
const listeners = new Set<Listener>();
let timeoutId: number | null = null;

export function showToast(message: string, durationMs = 2500) {
  listeners.forEach((fn) => fn(message));
  if (timeoutId !== null) {
    window.clearTimeout(timeoutId);
  }
  timeoutId = window.setTimeout(() => {
    listeners.forEach((fn) => fn(null));
    timeoutId = null;
  }, durationMs);
}

export function useToast() {
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => {
    listeners.add(setMessage);
    return () => {
      listeners.delete(setMessage);
    };
  }, []);
  return message;
}
