import type { Status } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { StatusBadge, type ReviewStatus } from "@/components/ui/status-badge";

const MAP: Record<string, ReviewStatus> = {
  verified: "verified",
  expert_reviewed: "expert_reviewed",
  official_regulatory: "official_regulatory",
  manufacturer_supplied: "manufacturer_supplied",
  source_found_pending_review: "pending_review",
  needs_verification: "needs_verification",
  deprecated: "deprecated",
};

export function StatusLine({ status }: { status: Status }) {
  const key: ReviewStatus = status.is_development_data
    ? "development"
    : (MAP[status.code] ?? "needs_verification");
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <StatusBadge status={key} />
      {!status.is_development_data && (
        <span className="text-xs text-muted">Reviewed {formatDate(status.reviewed_at)}</span>
      )}
    </span>
  );
}
