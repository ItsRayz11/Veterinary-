import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { Breadcrumbs, EmptyState, PageHeader } from "@/components/ui/primitives";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Species",
  description: "Browse veterinary drug references by species.",
  alternates: { canonical: "/species" },
};

interface SpeciesRow {
  slug: string;
  name: string;
  parent: string | null;
}

export default async function SpeciesIndex() {
  const rows = await apiGet<SpeciesRow[]>("/species/");
  const top = rows.filter((r) => !r.parent);
  return (
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Species" }]} />
      <PageHeader
        title="Species"
        lead="Reviewed references and catalogue records by animal group."
      />
      {rows.length === 0 ? (
        <EmptyState title="No species available." />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {top.map((s) => (
            <li key={s.slug} className="card p-4">
              <Link className="font-medium text-primary underline" href={`/species/${s.slug}`}>
                {s.name}
              </Link>
              <ul className="mt-2 flex flex-wrap gap-2 text-sm">
                {rows
                  .filter((c) => c.parent === s.slug)
                  .map((c) => (
                    <li key={c.slug}>
                      <Link
                        className="neo inline-block rounded-full px-3 py-1 text-primary"
                        href={`/species/${c.slug}`}
                      >
                        {c.name}
                      </Link>
                    </li>
                  ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
