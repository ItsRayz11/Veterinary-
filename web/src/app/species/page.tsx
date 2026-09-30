import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { Breadcrumbs, EmptyState } from "@/components/ui/primitives";

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
    <main className="space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Species" }]} />
      <h1 className="text-2xl font-semibold">Species</h1>
      {rows.length === 0 ? (
        <EmptyState title="No species available." />
      ) : (
        <ul className="space-y-3">
          {top.map((s) => (
            <li key={s.slug}>
              <Link className="font-medium text-primary underline" href={`/species/${s.slug}`}>
                {s.name}
              </Link>
              <ul className="ml-4 flex flex-wrap gap-x-4 text-sm">
                {rows
                  .filter((c) => c.parent === s.slug)
                  .map((c) => (
                    <li key={c.slug}>
                      <Link className="text-primary underline" href={`/species/${c.slug}`}>
                        {c.name}
                      </Link>
                    </li>
                  ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
