import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import { Breadcrumbs, EmptyState, PageHeader, Tile } from "@/components/ui/primitives";

export const dynamic = "force-dynamic";

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
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Countries" }]} />
      <PageHeader
        title="Countries"
        lead="Catalogue records by country. Imported entries are labelled until reviewed."
      />
      {rows.length === 0 ? (
        <EmptyState title="No countries available." />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {rows.map((c) => (
            <li key={c.iso2}>
              <Tile href={`/countries/${c.iso2}`} title={c.name} desc={`Prices in ${c.currency}`} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
