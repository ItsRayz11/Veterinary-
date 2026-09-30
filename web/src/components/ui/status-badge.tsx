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

const STYLES: Record<ReviewStatus, { label: string; cls: string }> = {
  verified: { label: "Verified", cls: "bg-ok-bg text-ok" },
  expert_reviewed: { label: "Expert reviewed", cls: "bg-ok-bg text-ok" },
  official_regulatory: { label: "Official regulatory source", cls: "bg-info-bg text-info" },
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
    <span className={`inline-block rounded-sm px-2 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}
