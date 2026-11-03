import Link from "next/link";
import { Building2, CalendarClock, MapPin } from "lucide-react";
import { IconChip } from "@/components/ui/icons";
import { EmptyState } from "@/components/ui/primitives";
import { MetadataBadge } from "@/components/ui/visual";
import { FUNDING, JOB_TYPES, LABELS, LEVELS, label, type Kind, type Listing } from "@/lib/listings";

function badges(l: Listing): string[] {
  const parts =
    l.kind === "jobs"
      ? [label(JOB_TYPES, l.job_type)]
      : [label(LEVELS, l.level), label(FUNDING, l.funding)];
  return parts.filter(Boolean);
}

export function ListingIndex({ kind, items }: { kind: Kind; items: Listing[] }) {
  const L = LABELS[kind];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{L.plural}</h1>
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
              <Link href={`/${kind}/${l.id}`} className="card card-link flex gap-3 p-4">
                <IconChip category={kind === "jobs" ? "jobs" : "scholarships"} />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{l.title}</span>
                  <span className="mt-0.5 flex items-center gap-1.5 text-sm text-muted">
                    <Building2 size={14} aria-hidden="true" />
                    {l.organization}
                  </span>
                  <span className="mt-2 flex flex-wrap items-center gap-1.5">
                    {badges(l).map((b) => (
                      <MetadataBadge key={b}>{b}</MetadataBadge>
                    ))}
                    {(l.city || l.country_name) && (
                      <MetadataBadge icon={MapPin}>
                        {[l.city, l.country_name].filter(Boolean).join(", ")}
                      </MetadataBadge>
                    )}
                    {l.closes_on && (
                      <MetadataBadge tone="amber" icon={CalendarClock}>
                        Closes {l.closes_on}
                      </MetadataBadge>
                    )}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
