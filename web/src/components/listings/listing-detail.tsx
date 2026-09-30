import Link from "next/link";
import { Alert, Breadcrumbs } from "@/components/ui/primitives";
import { FUNDING, JOB_TYPES, LABELS, LEVELS, label, type Kind, type Listing } from "@/lib/listings";
import { ReportButton } from "./report-button";

export function ListingDetail({ kind, item }: { kind: Kind; item: Listing }) {
  const L = LABELS[kind];
  const facts: [string, string][] =
    kind === "jobs"
      ? [
          ["Type", label(JOB_TYPES, item.job_type)],
          ["Location", [item.city, item.country_name].filter(Boolean).join(", ")],
        ]
      : [
          ["Level", label(LEVELS, item.level)],
          ["Funding", label(FUNDING, item.funding)],
          ["Country", item.country_name ?? ""],
        ];
  return (
    <main className="mx-auto max-w-2xl space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: L.plural, href: `/${kind}` },
          { label: item.title },
        ]}
      />
      <h1 className="text-2xl font-semibold">{item.title}</h1>
      <p className="text-sm text-muted">{item.organization}</p>
      <dl className="grid grid-cols-2 gap-2 text-sm">
        {facts
          .filter(([, v]) => v)
          .map(([k, v]) => (
            <div key={k}>
              <dt className="text-muted">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        {item.closes_on && (
          <div>
            <dt className="text-muted">Closes</dt>
            <dd>{item.closes_on}</dd>
          </div>
        )}
      </dl>
      <div className="space-y-3 text-sm leading-relaxed">
        {item.description
          .split(/\n\s*\n/)
          .filter(Boolean)
          .map((p, i) => (
            <p key={i}>{p}</p>
          ))}
      </div>
      <Alert tone="warn" title="Check before you apply">
        This listing was submitted by a user and checked by a moderator. We do not employ or fund
        anyone here. Never pay a fee to apply.
      </Alert>
      <p>
        <a
          className="inline-flex min-h-11 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-fg"
          href={item.apply_url}
          rel="noopener noreferrer nofollow ugc"
          target="_blank"
        >
          Go to the original posting
        </a>
      </p>
      <ReportButton kind={kind} id={item.id} />
      <p className="text-sm">
        <Link className="text-primary underline" href={`/${kind}`}>
          Back to {L.plural.toLowerCase()}
        </Link>
      </p>
    </main>
  );
}
