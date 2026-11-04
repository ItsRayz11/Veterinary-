import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { SpeciesPhoto, speciesCredit } from "@/components/ui/species-photo";
import { HelpTip } from "@/components/ui/help-tip";
import { RelatedResources } from "@/components/ui/visual";
import { Alert, Breadcrumbs, DataTable, EmptyState, td, th } from "@/components/ui/primitives";

interface SpeciesDetail {
  slug: string;
  name: string;
  is_food_producing: boolean;
  parent: { slug: string; name: string } | null;
  children: { slug: string; name: string }[];
  generics: { name: string; slug: string; drug_class: string | null; dose_count: number }[];
}

export async function generateMetadata({
  params,
}: PageProps<"/species/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const s = await apiGet<SpeciesDetail>(`/species/${slug}/`);
  return { title: s.name, alternates: { canonical: `/species/${s.slug}` } };
}

export default async function SpeciesPage({ params }: PageProps<"/species/[slug]">) {
  const { slug } = await params;
  const s = await apiGet<SpeciesDetail>(`/species/${slug}/`);
  return (
    <div className="space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Species", href: "/species" },
          ...(s.parent ? [{ label: s.parent.name, href: `/species/${s.parent.slug}` }] : []),
          { label: s.name },
        ]}
      />
      <div className="flex items-center gap-4">
        <SpeciesPhoto
          slug={s.slug}
          name={s.name}
          sizes="160px"
          priority
          className="h-24 w-32 shrink-0 rounded-xl sm:h-28 sm:w-40"
        />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{s.name}</h1>
          {speciesCredit(s.slug) && (
            <p className="mt-1 text-xs text-muted">
              Photo: {speciesCredit(s.slug)!.credit}, {speciesCredit(s.slug)!.license}.{" "}
              <Link href="/credits" className="underline">
                Credits
              </Link>
            </p>
          )}
        </div>
      </div>
      <RelatedResources
        items={[
          {
            href: "/calculators/dose-calculator",
            label: "Dose calculator",
            category: "calculators",
          },
          { href: "/classes", label: "Drug classes", category: "classes" },
          { href: "/countries", label: "Countries", category: "countries" },
        ]}
      />
      {s.is_food_producing && (
        <Alert tone="warn" title="Food-producing species">
          Withdrawal periods apply; see each product page.
        </Alert>
      )}
      {s.children.length > 0 && (
        <p className="flex flex-wrap gap-3 text-sm">
          {s.children.map((c) => (
            <Link key={c.slug} className="text-primary underline" href={`/species/${c.slug}`}>
              {c.name}
            </Link>
          ))}
        </p>
      )}
      <h2 className="flex items-center gap-1 font-semibold">
        Reviewed dosing
        <HelpTip label="About species dosing">
          Drugs appear here only when a sourced, veterinarian-reviewed dose exists for {s.name}.
          Doses are never copied from another species or inferred from a drug name.
        </HelpTip>
      </h2>
      {s.generics.length === 0 ? (
        <EmptyState title="No reviewed dosing published yet.">
          This is a coverage gap, not a statement that no drug is used.
        </EmptyState>
      ) : (
        <DataTable caption={`Drugs with reviewed doses for ${s.name}`}>
          <thead>
            <tr>
              <th className={th}>Drug</th>
              <th className={th}>Class</th>
              <th className={th}>Doses</th>
            </tr>
          </thead>
          <tbody>
            {s.generics.map((g) => (
              <tr key={g.slug}>
                <td className={td}>
                  <Link
                    className="text-primary underline"
                    href={`/drugs/${g.slug}?species=${s.slug}`}
                  >
                    {g.name}
                  </Link>
                </td>
                <td className={td}>{g.drug_class ?? ""}</td>
                <td className={td}>{g.dose_count}</td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      )}
    </div>
  );
}
