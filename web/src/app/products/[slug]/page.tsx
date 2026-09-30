import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, type ProductDetail } from "@/lib/api";
import { SourcesList } from "@/components/sources-list";
import { StatusLine } from "@/components/status-line";
import { Breadcrumbs, DataTable, EmptyState, Section, td, th } from "@/components/ui/primitives";

export async function generateMetadata({
  params,
}: PageProps<"/products/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const p = await apiGet<ProductDetail>(`/products/${slug}/`);
  return {
    title: `${p.brand_name} (${p.generic_name})`,
    alternates: { canonical: `/products/${p.slug}` },
  };
}

export default async function ProductPage({ params }: PageProps<"/products/[slug]">) {
  const { slug } = await params;
  const p = await apiGet<ProductDetail>(`/products/${slug}/`);

  return (
    <main className="space-y-6">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: p.generic_name, href: `/drugs/${p.generic}` },
          { label: p.brand_name },
        ]}
      />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{p.brand_name}</h1>
        <p className="text-sm text-muted">
          <Link href={`/drugs/${p.generic}`} className="underline">
            {p.generic_name}
          </Link>{" "}
          by{" "}
          <Link href={`/companies/${p.manufacturer.slug}`} className="underline">
            {p.manufacturer.name}
          </Link>
          {p.marketing_holder && ` · Marketing authorisation holder: ${p.marketing_holder}`}
        </p>
        <StatusLine status={p.status} />
      </header>

      <Section id="composition" title="Composition and presentations">
        <div className="grid gap-4 sm:grid-cols-2">
          <DataTable caption="Active ingredients and strengths">
            <thead>
              <tr>
                <th scope="col" className={th}>
                  Ingredient
                </th>
                <th scope="col" className={th}>
                  Strength
                </th>
              </tr>
            </thead>
            <tbody>
              {p.ingredients.map((i) => (
                <tr key={i.name}>
                  <th scope="row" className={td}>
                    {i.name}
                  </th>
                  <td className={td}>
                    {i.strength} {i.unit}
                    {i.per && ` per ${i.per_value === "1" ? "" : `${i.per_value} `}${i.per}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
          <DataTable caption="Available forms and pack sizes">
            <thead>
              <tr>
                <th scope="col" className={th}>
                  Form
                </th>
                <th scope="col" className={th}>
                  Pack size
                </th>
              </tr>
            </thead>
            <tbody>
              {p.packs.map((k) => (
                <tr key={`${k.form}-${k.size}-${k.unit}`}>
                  <th scope="row" className={td}>
                    {k.form}
                  </th>
                  <td className={td}>
                    {k.size} {k.unit}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </div>
      </Section>

      <Section id="availability" title="Country availability">
        {p.registrations.length ? (
          <DataTable caption="Registrations by country">
            <thead>
              <tr>
                {["Country", "Registration no.", "Status", "Record"].map((h) => (
                  <th key={h} scope="col" className={th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {p.registrations.map((r) => (
                <tr key={`${r.country}-${r.number}`}>
                  <th scope="row" className={td}>
                    {r.country}
                  </th>
                  <td className={td}>{r.number}</td>
                  <td className={td}>{r.status}</td>
                  <td className={td}>
                    <StatusLine status={r.record_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        ) : (
          <EmptyState title="No registration records" />
        )}
      </Section>

      <Section id="withdrawal" title="Withdrawal periods">
        {p.withdrawal_periods.length ? (
          <DataTable caption="Withdrawal periods by country, species and commodity">
            <thead>
              <tr>
                {["Country", "Species", "Commodity", "Route", "Period", "Status"].map((h) => (
                  <th key={h} scope="col" className={th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {p.withdrawal_periods.map((w) => (
                <tr key={`${w.country}-${w.species}-${w.commodity}-${w.route}`}>
                  <th scope="row" className={td}>
                    {w.country}
                  </th>
                  <td className={td}>{w.species}</td>
                  <td className={td}>{w.commodity}</td>
                  <td className={td}>{w.route}</td>
                  <td className={td}>
                    {w.duration_value} {w.duration_unit}
                  </td>
                  <td className={td}>
                    <StatusLine status={w.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        ) : (
          <EmptyState title="Verified withdrawal information is currently unavailable.">
            Withdrawal periods are shown only when confirmed by a regulator or a veterinary
            reviewer, and are specific to country, species and commodity.
          </EmptyState>
        )}
      </Section>

      <Section id="sources" title="Sources">
        <SourcesList sources={p.sources} />
      </Section>
    </main>
  );
}
