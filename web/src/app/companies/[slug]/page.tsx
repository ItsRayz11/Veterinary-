import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, type CompanyDetail } from "@/lib/api";
import { StatusLine } from "@/components/status-line";
import { Breadcrumbs, DataTable, EmptyState, Section, td, th } from "@/components/ui/primitives";

export async function generateMetadata({
  params,
}: PageProps<"/companies/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const c = await apiGet<CompanyDetail>(`/companies/${slug}/`);
  return { title: c.name, alternates: { canonical: `/companies/${c.slug}` } };
}

export default async function CompanyPage({ params }: PageProps<"/companies/[slug]">) {
  const { slug } = await params;
  const c = await apiGet<CompanyDetail>(`/companies/${slug}/`);
  const generics = [...new Map(c.products.map((p) => [p.generic, p.generic_name])).entries()];

  return (
    <div className="space-y-6">
      <Breadcrumbs
        items={[{ label: "Home", href: "/" }, { label: "Companies" }, { label: c.name }]}
      />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">{c.name}</h1>
        <p className="text-sm text-muted">
          {c.country}
          {c.roles.length > 0 && ` · ${c.roles.join(", ")}`}
          {c.website && (
            <>
              {" · "}
              <a
                href={c.website}
                rel="noopener noreferrer nofollow"
                target="_blank"
                className="underline"
              >
                Website
              </a>
            </>
          )}
        </p>
        <StatusLine status={c.status} />
        {c.verified_profile && <p className="text-xs text-ok">Verified company profile</p>}
        {c.description && <p className="text-sm">{c.description}</p>}
      </header>

      <Section id="products" title={`Product catalogue (${c.products.length})`}>
        {c.products.length ? (
          <DataTable caption={`Products from ${c.name}`}>
            <thead>
              <tr>
                {["Brand", "Generic", "Countries"].map((h) => (
                  <th key={h} scope="col" className={th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {c.products.map((p) => (
                <tr key={p.slug}>
                  <th scope="row" className={td}>
                    <Link href={`/products/${p.slug}`} className="text-primary underline">
                      {p.brand_name}
                    </Link>
                  </th>
                  <td className={td}>
                    <Link href={`/drugs/${p.generic}`} className="underline">
                      {p.generic_name}
                    </Link>
                  </td>
                  <td className={td}>{p.countries.join(", ") || "–"}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        ) : (
          <EmptyState title="No products listed" />
        )}
      </Section>

      {generics.length > 0 && (
        <Section id="portfolio" title="Generic portfolio">
          <ul className="flex flex-wrap gap-2 text-sm">
            {generics.map(([slug, name]) => (
              <li key={slug}>
                <Link
                  href={`/drugs/${slug}`}
                  className="rounded-sm bg-surface-2 px-2 py-1 underline"
                >
                  {name}
                </Link>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
