/**
 * Drawer — mobile nav slide-out (placeholder).
 *
 * Phase 5a ships a minimal stub since the bottom nav covers primary
 * navigation on mobile and the desktop nav covers everything else.
 * Phase 5b can flesh this out into the full drawer from the mockup
 * (sections: Browse / My archive / Beats with role-gated links).
 */

interface Props {
  open: boolean;
  onClose: () => void;
}

export function Drawer({ open, onClose }: Props) {
  if (!open) return null;
  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 99,
        }}
      />
      <div
        style={{
          position: "fixed", top: 0, left: 0, bottom: 0, width: "84%", maxWidth: 320,
          background: "var(--ta-surface)", zIndex: 100, padding: 16,
        }}
      >
        <h3 style={{ fontFamily: "Georgia, serif", marginBottom: 12 }}>Menu</h3>
        <nav style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <a href="#/" onClick={onClose}>Newsroom</a>
          <a href="#/civs" onClick={onClose}>Civilizations</a>
          <a href="#/inquisitions" onClick={onClose}>Inquisitions</a>
          <a href="#/timeline" onClick={onClose}>Timeline</a>
          <a href="#/dashboard" onClick={onClose}>Dashboard</a>
          <a href="#/drafts" onClick={onClose}>Drafts</a>
        </nav>
      </div>
    </>
  );
}
