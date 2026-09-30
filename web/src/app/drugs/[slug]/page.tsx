import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, type GenericDetail } from "@/lib/api";
import { formatDoseRange, formatDuration, formatFrequency } from "@/lib/format";
import { SourcesList } from "@/components/sources-list";
import { StatusLine } from "@/components/status-line";
import {
  Alert,
  Breadcrumbs,
  DataTable,
  EmptyState,
  Section,
  SectionNav,
  td,
  th,
} from "@/components/ui/primitives";

const KIND: Record<string, string> = {
  contraindication: "Contraindications",
  precaution: "Precautions",
  adverse_effect: "Adverse effects",
  toxicity: "Toxicity",
  warning: "Warnings",
};

export async function generateMetadata({ params }: PageProps<"/drugs/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const g = await apiGet<GenericDetail>(`/generics/${slug}/`);
  return {
    title: g.name,
    description: `${g.name}: species doses, safety notes, brands and sources.`,
    alternates: { canonical: `/drugs/${g.slug}` },
  };
}

export default async function DrugPage({ params, searchParams }: PageProps<"/drugs/[slug]">) {
  const { slug } = await params;
  const sp = await searchParams;
  const country = typeof sp.country === "string" ? sp.country : "";
  const species = typeof sp.species === "string" ? sp.species : "";
  const qs = new URLSearchParams();
  if (country) qs.set("country", country);
  if (species) qs.set("species", species);
  const g = await apiGet<GenericDetail>(`/generics/${slug}/${qs.size ? `?${qs}` : ""}`);

  const speciesInDoses = [...new Map(g.doses.map((d) => [d.species, d.species_name])).entries()];
  const notesByKind = Object.entries(KIND)
    .map(([kind, label]) => ({ label, items: g.notes.filter((n) => n.kind === kind) }))
    .filter((k) => k.items.length);

  return (
    <main className="space-y-6">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Drugs" }, { label: g.name }]} />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{g.name}</h1>
        <p className="text-sm text-muted">
          {[g.drug_class, g.ingredients.length > 1 ? g.ingredients.join(" + ") : null]
            .filter(Boolean)
            .join(" · ") || "Generic medicine"}
          {g.synonyms.length > 0 && ` · Also: ${g.synonyms.join(", ")}`}
        </p>
        <StatusLine status={g.status} />
      </header>
      <Alert tone="warn" title="Reference only">
        {g.disclaimer}
      </Alert>
      <SectionNav
        items={[
          { id: "overview", label: "Overview" },
          { id: "dosing", label: "Dosing" },
          { id: "safety", label: "Safety" },
          { id: "brands", label: `Brands (${g.brands.length})` },
          { id: "sources", label: "Sources" },
        ]}
      />

      <Section id="overview" title="Overview">
        {g.description || g.mechanism ? (
          <div className="space-y-2 text-sm">
            {g.description && <p>{g.description}</p>}
            {g.mechanism && (
              <p>
                <span className="font-medium">Mechanism: </span>
                {g.mechanism}
              </p>
            )}
          </div>
        ) : (
          <EmptyState title="No overview available yet" />
        )}
      </Section>

      <Section id="dosing" title="Dosing by species">
        {speciesInDoses.length > 0 && (
          <p className="mb-2 flex flex-wrap gap-2 text-sm">
            <Link
              href={`/drugs/${g.slug}`}
              className={species ? "text-primary underline" : "font-medium"}
            >
              All species
            </Link>
            {speciesInDoses.map(([s, name]) => (
              <Link
                key={s}
                href={`/drugs/${g.slug}?species=${s}`}
                className={species === s ? "font-medium" : "text-primary underline"}
              >
                {name}
              </Link>
            ))}
          </p>
        )}
        {g.doses.length ? (
          <DataTable caption={`Reference doses for ${g.name}`}>
            <thead>
              <tr>
                {[
                  "Species",
                  "Indication",
                  "Route",
                  "Dose",
                  "Frequency",
                  "Duration",
                  "Status",
                  "",
                ].map((h, i) => (
                  <th key={`${h}-${i}`} scope="col" className={th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {g.doses.map((d) => (
                <tr key={d.id}>
                  <th scope="row" className={`${td} font-medium`}>
                    {d.species_name}
                  </th>
                  <td className={td}>{d.indication ?? "–"}</td>
                  <td className={td}>{d.route}</td>
                  <td className={td}>
                    {formatDoseRange(d)}
                    {d.max_single_dose && (
                      <span className="block text-xs text-muted">
                        max {d.max_single_dose} {d.max_single_dose_unit}
                      </span>
                    )}
                  </td>
                  <td className={td}>{formatFrequency(d.interval_hours)}</td>
                  <td className={td}>{formatDuration(d)}</td>
                  <td className={td}>
                    <StatusLine status={d.status} />
                    {d.sources.length > 0 && (
                      <span className="block text-xs text-muted">
                        {d.sources.map((s) => s.title).join("; ")}
                      </span>
                    )}
                  </td>
                  <td className={td}>
                    {d.calculator_ready && (
                      <Link
                        className="whitespace-nowrap text-primary underline"
                        href={`/calculators/dose-calculator?${new URLSearchParams({
                          dose: d.dose_min,
                          dose_max: d.dose_max,
                          label: `${g.name}, ${d.species_name}, ${d.route}`,
                        })}`}
                      >
                        Calculate
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        ) : (
          <EmptyState title="Verified dosing information is currently unavailable.">
            Doses appear here only after they have a source and have been reviewed.
          </EmptyState>
        )}
      </Section>

      <Section id="safety" title="Safety">
        {notesByKind.length ? (
          <div className="space-y-4">
            {notesByKind.map((k) => (
              <div key={k.label}>
                <h3 className="text-sm font-medium">{k.label}</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                  {k.items.map((n) => (
                    <li key={n.id}>
                      {n.text} <StatusLine status={n.status} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No reviewed safety information yet" />
        )}
      </Section>

      <Section id="brands" title={`Brands (${g.brands.length})`}>
        <p className="mb-2 flex flex-wrap gap-2 text-sm">
          <Link
            href={`/drugs/${g.slug}`}
            className={country ? "text-primary underline" : "font-medium"}
          >
            All countries
          </Link>
          {["PK", "IN"].map((c) => (
            <Link
              key={c}
              href={`/drugs/${g.slug}?country=${c}`}
              className={country === c ? "font-medium" : "text-primary underline"}
            >
              {c === "PK" ? "Pakistan" : "India"}
            </Link>
          ))}
        </p>
        {g.brands.length ? (
          <DataTable caption={`Brands containing ${g.name}`}>
            <thead>
              <tr>
                {["Brand", "Manufacturer", "Countries", "Status"].map((h) => (
                  <th key={h} scope="col" className={th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {g.brands.map((b) => (
                <tr key={b.slug}>
                  <th scope="row" className={td}>
                    <Link href={`/products/${b.slug}`} className="text-primary underline">
                      {b.brand_name}
                    </Link>
                  </th>
                  <td className={td}>
                    <Link href={`/companies/${b.manufacturer.slug}`} className="underline">
                      {b.manufacturer.name}
                    </Link>
                  </td>
                  <td className={td}>{b.countries.join(", ") || "–"}</td>
                  <td className={td}>
                    <StatusLine status={b.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        ) : (
          <EmptyState title="No brands listed for this selection" />
        )}
      </Section>

      <Section id="sources" title="Sources">
        <SourcesList sources={g.sources} />
      </Section>
    </main>
  );
}
