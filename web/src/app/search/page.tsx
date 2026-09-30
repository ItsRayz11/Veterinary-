import type { Metadata } from "next";
import Link from "next/link";
import { ApiError, apiGet } from "@/lib/api";
import { SearchBox } from "@/components/search-box";
import { Alert, EmptyState } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Search", robots: { index: false } };

interface Results {
  generics: { name: string; slug: string }[];
  products: { name: string; slug: string; generic: string; manufacturer: string }[];
  companies: { name: string; slug: string }[];
  did_you_mean: string[];
}

export default async function SearchPage({ searchParams }: PageProps<"/search">) {
  const sp = await searchParams;
  const q = typeof sp.q === "string" ? sp.q : "";
  let results: Results | null = null;
  let failed = false;
  if (q.trim().length >= 2) {
    try {
      results = await apiGet<Results>(`/search/?q=${encodeURIComponent(q)}`, 0);
    } catch (e) {
      if (!(e instanceof ApiError)) throw e;
      failed = true;
    }
  }
  const none =
    results && !results.generics.length && !results.products.length && !results.companies.length;

  return (
    <main className="space-y-4">
      <h1 className="text-xl font-semibold">Search</h1>
      <SearchBox autoFocus />
      {failed && (
        <Alert tone="danger">Search is unavailable right now. Please try again shortly.</Alert>
      )}
      {q && !results && !failed && (
        <p className="text-sm text-muted">Type at least 2 characters.</p>
      )}
      {none && (
        <EmptyState title={`No results for “${q}”`}>
          {results!.did_you_mean.length > 0 && (
            <>
              Did you mean{" "}
              {results!.did_you_mean.map((n) => (
                <Link key={n} href={`/search?q=${encodeURIComponent(n)}`} className="underline">
                  {n}
                </Link>
              ))}
              ?
            </>
          )}
        </EmptyState>
      )}
      {results && (
        <div className="space-y-4">
          <Group
            title="Generics"
            items={results.generics.map((g) => ({ href: `/drugs/${g.slug}`, main: g.name }))}
          />
          <Group
            title="Brands"
            items={results.products.map((p) => ({
              href: `/products/${p.slug}`,
              main: p.name,
              sub: `${p.generic} · ${p.manufacturer}`,
            }))}
          />
          <Group
            title="Companies"
            items={results.companies.map((c) => ({ href: `/companies/${c.slug}`, main: c.name }))}
          />
        </div>
      )}
    </main>
  );
}

function Group({
  title,
  items,
}: {
  title: string;
  items: { href: string; main: string; sub?: string }[];
}) {
  if (!items.length) return null;
  return (
    <section>
      <h2 className="text-sm font-medium uppercase tracking-wide text-muted">{title}</h2>
      <ul className="mt-1 divide-y divide-border rounded-md border border-border bg-surface">
        {items.map((i) => (
          <li key={i.href}>
            <Link href={i.href} className="block px-3 py-2 hover:bg-surface-2">
              <span className="font-medium">{i.main}</span>
              {i.sub && <span className="ml-2 text-sm text-muted">{i.sub}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
