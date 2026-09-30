import Link from "next/link";
import { EmptyState } from "@/components/ui/primitives";
import { FUNDING, JOB_TYPES, LABELS, LEVELS, label, type Kind, type Listing } from "@/lib/listings";

function meta(l: Listing): string {
  const parts = [l.organization];
  if (l.kind === "jobs") parts.push(label(JOB_TYPES, l.job_type), l.city ?? "");
  else parts.push(label(LEVELS, l.level), label(FUNDING, l.funding));
  parts.push(l.country_name ?? "");
  return parts.filter(Boolean).join(" · ");
}

export function ListingIndex({ kind, items }: { kind: Kind; items: Listing[] }) {
  const L = LABELS[kind];
  return (
    <main className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">{L.plural}</h1>
        <Link className="text-primary underline" href={L.newPath}>
          Post a {L.singular}
        </Link>
      </div>
      <p className="text-sm text-muted">
        Listings are submitted by users and checked by moderators. Always confirm details with the
        employer or provider and never pay to apply.
      </p>
      {items.length === 0 ? (
        <EmptyState title={`No ${L.plural.toLowerCase()} are listed right now.`}>
          Approved listings appear here until their closing date.
        </EmptyState>
      ) : (
        <ul className="space-y-2">
          {items.map((l) => (
            <li key={l.id}>
              <Link
                href={`/${kind}/${l.id}`}
                className="block rounded-md border border-border bg-surface p-3 hover:border-primary"
              >
                <span className="font-medium">{l.title}</span>
                <span className="block text-sm text-muted">{meta(l)}</span>
                {l.closes_on && (
                  <span className="block text-xs text-muted">Closes {l.closes_on}</span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
