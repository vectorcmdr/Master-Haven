/** Toast — bottom-of-screen flash, driven by useToast. */
import { useToast } from "../hooks/useToast";

export function Toast() {
  const message = useToast();
  return (
    <div className={`ta-toast${message ? " show" : ""}`}>{message ?? ""}</div>
  );
}
