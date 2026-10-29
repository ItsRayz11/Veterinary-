import type { Metadata } from "next";
import { apiGet, type Brand } from "@/lib/api";
import { ProductTable } from "@/components/product-table";
import { Alert, Breadcrumbs, EmptyState, PageHeader } from "@/components/ui/primitives";

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
      <PageHeader title={c.name} lead={c.regulator ? `Regulator: ${c.regulator}` : undefined} />
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
        <ProductTable products={c.products} caption={`Products listed for ${c.name}`} />
      )}
    </div>
  );
}
