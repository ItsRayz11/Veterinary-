import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, type Brand, type Page, type UniversityBrief } from "@/lib/api";
import { ProductTable } from "@/components/product-table";
import { Alert, Breadcrumbs, EmptyState } from "@/components/ui/primitives";
import { CountryHero } from "@/components/ui/visual";

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
  return {
    title: `Veterinary products in ${c.name}`,
    description: `${c.products.length} veterinary products listed for ${c.name}${
      c.regulator ? `, with regulator ${c.regulator}` : ""
    }. Imported entries are labelled until reviewed.`,
    alternates: { canonical: `/countries/${c.iso2}` },
  };
}

const PAGE_SIZE = 50;

export default async function CountryPage({
  params,
  searchParams,
}: PageProps<"/countries/[iso2]">) {
  const { iso2 } = await params;
  const sp = await searchParams;
  const c = await apiGet<CountryDetail>(`/countries/${iso2}/`);
  const universities = await apiGet<Page<UniversityBrief>>(
    `/universities/?country=${c.iso2}`,
  ).catch(() => null);
  const pages = Math.max(1, Math.ceil(c.products.length / PAGE_SIZE));
  const raw = Number(Array.isArray(sp.page) ? sp.page[0] : sp.page);
  const page = Number.isInteger(raw) && raw >= 1 ? Math.min(raw, pages) : 1;
  const shown = c.products.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const href = (n: number) => `/countries/${c.iso2}?page=${n}`;
  return (
    <div className="space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Countries", href: "/countries" },
          { label: c.name },
        ]}
      />
      <CountryHero
        iso2={c.iso2}
        name={c.name}
        regulator={c.regulator || undefined}
        currency={c.currency || undefined}
        productCount={c.products.length}
        universityCount={universities?.count}
      />
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
        <>
          <ProductTable products={shown} caption={`Products listed for ${c.name}`} />
          {pages > 1 && (
            <nav aria-label="Pagination" className="flex items-center justify-between text-sm">
              {page > 1 ? (
                <Link className="neo rounded-full px-3 py-2" href={href(page - 1)} rel="prev">
                  Previous
                </Link>
              ) : (
                <span />
              )}
              <span aria-live="polite">
                Page {page} of {pages}
              </span>
              {page < pages ? (
                <Link className="neo rounded-full px-3 py-2" href={href(page + 1)} rel="next">
                  Next
                </Link>
              ) : (
                <span />
              )}
            </nav>
          )}
        </>
      )}
    </div>
  );
}
