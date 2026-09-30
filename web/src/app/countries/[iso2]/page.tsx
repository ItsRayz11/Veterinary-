import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, type Brand } from "@/lib/api";
import { Alert, Breadcrumbs, DataTable, EmptyState, td, th } from "@/components/ui/primitives";
import { StatusBadge } from "@/components/ui/status-badge";

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
    <div className="space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Countries", href: "/countries" },
          { label: c.name },
        ]}
      />
      <h1 className="text-2xl font-semibold">{c.name}</h1>
      {c.regulator && <p className="text-sm text-muted">Regulator: {c.regulator}</p>}
      {c.products.some((p) => p.status.is_unverified_import) && (
        <Alert tone="warn" title="Some entries are imported, not reviewed">
          Entries marked &ldquo;Imported, not reviewed&rdquo; come from the regulator&apos;s public
          lists of applications. They are not confirmed registrations and have not been checked by a
          reviewer.
        </Alert>
      )}
      {c.products.length === 0 ? (
        <EmptyState title={`No reviewed registrations for ${c.name} yet.`}>
          Products appear here only when a reviewed registration exists for this country.
        </EmptyState>
      ) : (
        <DataTable caption={`Products listed for ${c.name}`}>
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
                  {p.status.is_unverified_import && (
                    <span className="ml-2 align-middle">
                      <StatusBadge status="imported" />
                    </span>
                  )}
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
    </div>
  );
}
