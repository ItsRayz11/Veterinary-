import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, apiGetAll, type UniversityBrief } from "@/lib/api";
import { Flag } from "@/components/ui/flag";
import { Breadcrumbs, EmptyState, PageHeader } from "@/components/ui/primitives";
import { UniversityCard } from "@/components/ui/university-card";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Veterinary universities",
  description:
    "Veterinary schools and faculties by country, with official websites and linked past papers.",
  alternates: { canonical: "/universities" },
};

interface CountryRow {
  iso2: string;
  name: string;
}

export default async function UniversitiesIndex({ searchParams }: PageProps<"/universities">) {
  const sp = await searchParams;
  const country = typeof sp.country === "string" ? sp.country.toUpperCase() : "";
  const [rows, countries] = await Promise.all([
    apiGetAll<UniversityBrief>(`/universities/${country ? `?country=${country}` : ""}`),
    apiGet<CountryRow[]>("/countries/"),
  ]);
  const byCountry = new Map<string, UniversityBrief[]>();
  for (const u of rows)
    byCountry.set(u.country_name, [...(byCountry.get(u.country_name) ?? []), u]);

  return (
    <div className="space-y-5">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Universities" }]} />
      <PageHeader
        title="Veterinary universities"
        lead="Veterinary schools and faculties. Records are imported from open sources and labelled until reviewed."
      />
      <nav aria-label="Filter by country">
        <ul className="flex flex-wrap gap-2 text-sm">
          <li>
            <Link
              href="/universities"
              aria-current={country ? undefined : "page"}
              className={`neo inline-flex min-h-9 items-center rounded-full px-3 ${country ? "" : "font-semibold text-primary"}`}
            >
              All countries
            </Link>
          </li>
          {countries.map((c) => (
            <li key={c.iso2}>
              <Link
                href={`/universities?country=${c.iso2}`}
                aria-current={country === c.iso2 ? "page" : undefined}
                className={`neo inline-flex min-h-9 items-center gap-1.5 rounded-full px-3 ${country === c.iso2 ? "font-semibold text-primary" : ""}`}
              >
                <Flag iso2={c.iso2} className="h-3.5 w-5" />
                {c.name}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {rows.length === 0 ? (
        <EmptyState title="No universities listed for this selection yet.">
          Records are imported from Wikipedia and Wikidata by an administrator and appear here once
          they exist.
        </EmptyState>
      ) : (
        [...byCountry.entries()].map(([name, list]) => (
          <section key={name} aria-label={name} className="space-y-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
              <Flag iso2={list[0].country} name={name} className="h-5 w-7" />
              {name}
              <span className="text-sm font-normal text-muted">({list.length})</span>
            </h2>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {list.map((u) => (
                <li key={u.slug}>
                  <UniversityCard uni={u} />
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
