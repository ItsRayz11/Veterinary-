import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, type Brand } from "@/lib/api";
import { Breadcrumbs, DataTable, EmptyState, td, th } from "@/components/ui/primitives";

interface CountryDetail {
  iso2: string;
  name: string;
  currency: string;
  regulator: string;
  products: Brand[];
}

export async function generateMetadata({
  params,
}: PageProps<"/countries/[iso2]">): Promise<Metadata> {
  const { iso2 } = await params;
  const c = await apiGet<CountryDetail>(`/countries/${iso2}/`);
  return { title: `Products in ${c.name}`, alternates: { canonical: `/countries/${c.iso2}` } };
}

export default async function CountryPage({ params }: PageProps<"/countries/[iso2]">) {
  const { iso2 } = await params;
  const c = await apiGet<CountryDetail>(`/countries/${iso2}/`);
  return (
    <main className="space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Countries", href: "/countries" },
          { label: c.name },
        ]}
      />
      <h1 className="text-2xl font-semibold">{c.name}</h1>
      {c.regulator && <p className="text-sm text-muted">Regulator: {c.regulator}</p>}
      {c.products.length === 0 ? (
        <EmptyState title={`No reviewed registrations for ${c.name} yet.`}>
          Products appear here only when a reviewed registration exists for this country.
        </EmptyState>
      ) : (
        <DataTable caption={`Products registered in ${c.name}`}>
          <thead>
            <tr>
              <th className={th}>Brand</th>
              <th className={th}>Generic</th>
              <th className={th}>Manufacturer</th>
            </tr>
          </thead>
          <tbody>
            {c.products.map((p) => (
              <tr key={p.slug}>
                <td className={td}>
                  <Link className="text-primary underline" href={`/products/${p.slug}`}>
                    {p.brand_name}
                  </Link>
                </td>
                <td className={td}>
                  <Link className="text-primary underline" href={`/drugs/${p.generic}`}>
                    {p.generic_name}
                  </Link>
                </td>
                <td className={td}>
                  <Link
                    className="text-primary underline"
                    href={`/companies/${p.manufacturer.slug}`}
                  >
                    {p.manufacturer.name}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      )}
    </main>
  );
}
