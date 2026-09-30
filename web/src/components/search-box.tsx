"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

interface Results {
  generics: { name: string; slug: string }[];
  products: { name: string; slug: string; generic: string; manufacturer: string }[];
  companies: { name: string; slug: string }[];
  did_you_mean: string[];
}

export function SearchBox({ autoFocus = false }: { autoFocus?: boolean }) {
  const [q, setQ] = useState("");
  const [fetched, setResults] = useState<Results | null>(null);
  const [error, setError] = useState(false);
  const router = useRouter();
  const listId = useId();
  const seq = useRef(0);

  useEffect(() => {
    if (q.trim().length < 2) return;
    const mine = ++seq.current;
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/v1/search?q=${encodeURIComponent(q)}`);
        if (!res.ok) throw new Error();
        const data = (await res.json()) as Results;
        if (mine === seq.current) {
          setResults(data);
          setError(false);
        }
      } catch {
        if (mine === seq.current) setError(true);
      }
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  // Derived, not stored: clearing the box hides stale results without a setState-in-effect.
  const results = q.trim().length >= 2 ? fetched : null;
  const empty =
    results && !results.generics.length && !results.products.length && !results.companies.length;

  return (
    <div className="relative w-full">
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
        }}
      >
        <label htmlFor="global-search" className="sr-only">
          Search medicines, brands, companies
        </label>
        <input
          id="global-search"
          type="search"
          value={q}
          autoFocus={autoFocus}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search medicines, brands, companies…"
          aria-controls={listId}
          autoComplete="off"
          className="h-11 w-full rounded-md border border-border bg-surface px-3 text-base"
        />
      </form>
      <div id={listId} aria-live="polite">
        {error && <p className="mt-1 text-sm text-danger">Search is unavailable right now.</p>}
        {results && (
          <div className="absolute left-0 right-0 z-20 mt-1 max-h-[70vh] overflow-y-auto rounded-md border border-border bg-surface p-2 shadow-lg">
            {empty && (
              <p className="p-2 text-sm text-muted">
                No results.
                {results.did_you_mean.length > 0 && (
                  <>
                    {" "}
                    Did you mean{" "}
                    {results.did_you_mean.map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setQ(n)}
                        className="mr-1 font-medium text-primary underline"
                      >
                        {n}
                      </button>
                    ))}
                    ?
                  </>
                )}
              </p>
            )}
            <Group title="Generics">
              {results.generics.map((g) => (
                <Row key={g.slug} href={`/drugs/${g.slug}`} main={g.name} />
              ))}
            </Group>
            <Group title="Brands">
              {results.products.map((p) => (
                <Row
                  key={p.slug}
                  href={`/products/${p.slug}`}
                  main={p.name}
                  sub={`${p.generic} · ${p.manufacturer}`}
                />
              ))}
            </Group>
            <Group title="Companies">
              {results.companies.map((c) => (
                <Row key={c.slug} href={`/companies/${c.slug}`} main={c.name} />
              ))}
            </Group>
          </div>
        )}
      </div>
    </div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode[] }) {
  if (!children.length) return null;
  return (
    <div className="py-1">
      <p className="px-2 text-xs font-medium uppercase tracking-wide text-muted">{title}</p>
      <ul>{children}</ul>
    </div>
  );
}

function Row({ href, main, sub }: { href: string; main: string; sub?: string }) {
  return (
    <li>
      <Link href={href} className="block rounded-sm px-2 py-2 hover:bg-surface-2">
        <span className="font-medium">{main}</span>
        {sub && <span className="ml-2 text-sm text-muted">{sub}</span>}
      </Link>
    </li>
  );
}
