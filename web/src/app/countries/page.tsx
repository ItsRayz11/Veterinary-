import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { Breadcrumbs, EmptyState } from "@/components/ui/primitives";

export const metadata: Metadata = {
  title: "Countries",
  description: "Registered veterinary products by country.",
  alternates: { canonical: "/countries" },
};

interface CountryRow {
  iso2: string;
  name: string;
  currency: string;
}

export default async function CountriesIndex() {
  const rows = await apiGet<CountryRow[]>("/countries/");
  return (
    <main className="space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Countries" }]} />
      <h1 className="text-2xl font-semibold">Countries</h1>
      {rows.length === 0 ? (
        <EmptyState title="No countries available." />
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {rows.map((c) => (
            <li key={c.iso2}>
              <Link
                href={`/countries/${c.iso2}`}
                className="block rounded-md border border-border bg-surface p-3 hover:border-primary"
              >
                <span className="font-medium">{c.name}</span>
                <span className="block text-sm text-muted">Prices in {c.currency}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
