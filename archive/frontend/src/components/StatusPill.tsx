/** StatusPill — draft status indicator. */

const LABEL: Record<string, string> = {
  draft: "Draft",
  in_review: "In review",
  returned: "Returned",
  ready: "Ready to publish",
  published: "Published",
};

export function StatusPill({ status }: { status: string }) {
  return <span className={`ta-status ta-status-${status}`}>{LABEL[status] || status}</span>;
}
