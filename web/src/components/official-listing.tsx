import type { Provenance, Status } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { Alert } from "@/components/ui/primitives";

/** Shown on pages built from regulator data that no clinician has reviewed. */
export function OfficialListingNotice({
  status,
  listingKind,
  what,
}: {
  status: Status;
  listingKind?: string;
  what: string;
}) {
  if (status.tier !== "official_listing") return null;
  const application = listingKind === "application";
  return (
    <Alert
      tone="info"
      title={
        application
          ? "Application for registration, not an approval"
          : "Official regulatory listing, not clinically reviewed"
      }
    >
      {application
        ? `This ${what} appears in a regulator's list of applications. An application is not proof of registration or availability. `
        : `This ${what} is a factual entry from a regulator's public data (name, company, authorisation number, status). `}
      It has not been reviewed by a clinician and contains no dosing or treatment advice. Check the
      product label and the regulator before using any medicine.
    </Alert>
  );
}

/** Regulator, jurisdiction, status, source link, last check, review state, and licence credit. */
export function ProvenanceList({ items }: { items: Provenance[] }) {
  const seen = new Set<string>();
  const rows = items.filter((p) => {
    const key = `${p.regulator}|${p.jurisdiction_code}|${p.source_url}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  if (!rows.length) return null;
  return (
    <ul className="space-y-3 text-sm" aria-label="Where this information comes from">
      {rows.map((p) => (
        <li key={`${p.jurisdiction_code}-${p.source_url}`} className="rounded-md bg-surface-2 p-3">
          <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[10rem_1fr]">
            <dt className="text-muted">Regulator</dt>
            <dd>{p.regulator || "Not stated"}</dd>
            <dt className="text-muted">Jurisdiction</dt>
            <dd>{p.jurisdiction}</dd>
            <dt className="text-muted">Source</dt>
            <dd>
              {p.source_url ? (
                <a href={p.source_url} rel="noopener noreferrer nofollow" className="underline">
                  {p.source_url.replace(/^https?:\/\//, "")}
                </a>
              ) : (
                "No public link"
              )}
            </dd>
            <dt className="text-muted">Last checked</dt>
            <dd>{p.last_checked_at ? formatDate(p.last_checked_at) : "Not yet checked"}</dd>
            <dt className="text-muted">Clinical review</dt>
            <dd>{p.clinical_review}</dd>
          </dl>
          {p.attribution && (
            <p className="mt-2 text-xs text-muted">
              {p.attribution}
              {p.licence_url && (
                <>
                  {" "}
                  <a href={p.licence_url} rel="noopener noreferrer" className="underline">
                    Licence
                  </a>
                </>
              )}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
