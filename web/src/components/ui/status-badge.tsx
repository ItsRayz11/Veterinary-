/** Verification states from docs/CLINICAL_GOVERNANCE.md, plus a dev-data marker. */
export type ReviewStatus =
  | "verified"
  | "expert_reviewed"
  | "official_regulatory"
  | "manufacturer_supplied"
  | "pending_review"
  | "needs_verification"
  | "imported"
  | "deprecated"
  | "development";

/** Statements a reviewer has signed off. Everything else shows the hollow review mark. */
const REVIEWED: ReadonlySet<ReviewStatus> = new Set(["verified", "expert_reviewed"]);

const STYLES: Record<ReviewStatus, { label: string; cls: string }> = {
  verified: { label: "Verified", cls: "bg-ok-bg text-ok" },
  expert_reviewed: { label: "Expert reviewed", cls: "bg-ok-bg text-ok" },
  official_regulatory: {
    label: "Official listing, not clinically reviewed",
    cls: "bg-info-bg text-info",
  },
  manufacturer_supplied: { label: "Manufacturer supplied", cls: "bg-info-bg text-info" },
  pending_review: { label: "Pending review", cls: "bg-warn-bg text-warn" },
  needs_verification: { label: "Needs verification", cls: "bg-warn-bg text-warn" },
  imported: { label: "Imported, not reviewed", cls: "bg-warn-bg text-warn" },
  deprecated: { label: "Deprecated", cls: "bg-danger-bg text-danger" },
  development: { label: "Development data, not verified", cls: "bg-warn-bg text-warn" },
};

export function StatusBadge({ status }: { status: ReviewStatus }) {
  const { label, cls } = STYLES[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      <span
        className="review-mark"
        data-reviewed={REVIEWED.has(status) ? "true" : "false"}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
