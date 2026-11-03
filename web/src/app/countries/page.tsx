import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import { Flag } from "@/components/ui/flag";
import { Breadcrumbs, EmptyState, PageHeader } from "@/components/ui/primitives";
import { FeatureCard } from "@/components/ui/visual";

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
              <FeatureCard
                layout="row"
                href={`/countries/${c.iso2}`}
                category="countries"
                title={c.name}
                desc={`Prices in ${c.currency}`}
                lead={<Flag iso2={c.iso2} className="h-10 w-14 text-xs" />}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
