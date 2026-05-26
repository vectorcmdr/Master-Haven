/** Toast — bottom-of-screen flash, driven by useToast.
 *
 * Has `role="status"` and `aria-live="polite"` so screen readers
 * announce changes without stealing focus.
 */
import { useToast } from "../hooks/useToast";

export function Toast() {
  const message = useToast();
  return (
    <div
      className={`ta-toast${message ? " show" : ""}`}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {message ?? ""}
    </div>
  );
}
