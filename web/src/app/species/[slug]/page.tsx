import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
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
      <h1 className="text-2xl font-semibold">{s.name}</h1>
      {s.is_food_producing && (
        <Alert tone="warn" title="Food-producing species">
          Withdrawal periods apply. They are shown per product, per country, on each product page.
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
      <h2 className="font-semibold">Drugs with reviewed dosing for {s.name}</h2>
      {s.generics.length === 0 ? (
        <EmptyState title="No reviewed dosing is published for this species yet.">
          Doses appear here only after they are sourced and reviewed.
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
