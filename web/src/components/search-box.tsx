"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { CategoryIcon, type CategoryName } from "@/components/ui/icons";

interface Results {
  generics: { name: string; slug: string }[];
  products: { name: string; slug: string; generic: string; manufacturer: string }[];
  companies: { name: string; slug: string }[];
  did_you_mean: string[];
}

interface Item {
  href: string;
  main: string;
  sub?: string;
  category: CategoryName;
}

const GROUPS: { title: string; category: CategoryName }[] = [
  { title: "Generics", category: "medicines" },
  { title: "Brands", category: "vaccines" },
  { title: "Companies", category: "companies" },
];

export function SearchBox({ autoFocus = false }: { autoFocus?: boolean }) {
  const [q, setQ] = useState("");
  const [fetched, setResults] = useState<Results | null>(null);
  const [error, setError] = useState(false);
  const [active, setActive] = useState(-1);
  const [dismissed, setDismissed] = useState(false);
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
  const results = q.trim().length >= 2 && !dismissed ? fetched : null;
  const empty =
    results && !results.generics.length && !results.products.length && !results.companies.length;

  const groups: Item[][] = results
    ? [
        results.generics.map((g) => ({
          href: `/drugs/${g.slug}`,
          main: g.name,
          category: GROUPS[0].category,
        })),
        results.products.map((p) => ({
          href: `/products/${p.slug}`,
          main: p.name,
          sub: `${p.generic} · ${p.manufacturer}`,
          category: GROUPS[1].category,
        })),
        results.companies.map((c) => ({
          href: `/companies/${c.slug}`,
          main: c.name,
          category: GROUPS[2].category,
        })),
      ]
    : [];
  const flat = groups.flat();
  const optionId = (i: number) => `${listId}-opt-${i}`;

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      setDismissed(true);
      setActive(-1);
    } else if (e.key === "ArrowDown" && flat.length) {
      e.preventDefault();
      setActive((a) => (a + 1) % flat.length);
    } else if (e.key === "ArrowUp" && flat.length) {
      e.preventDefault();
      setActive((a) => (a <= 0 ? flat.length - 1 : a - 1));
    }
  }

  let index = 0;
  return (
    <div className="relative w-full">
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          if (active >= 0 && flat[active]) {
            router.push(flat[active].href);
            return;
          }
          if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
        }}
      >
        <label htmlFor="global-search" className="sr-only">
          Search medicines, brands, companies
        </label>
        <div className="relative">
          <CategoryIcon
            category="search"
            size={18}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
          />
          <input
            id="global-search"
            type="search"
            role="combobox"
            aria-expanded={!!results}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={active >= 0 ? optionId(active) : undefined}
            value={q}
            autoFocus={autoFocus}
            onChange={(e) => {
              setQ(e.target.value);
              setActive(-1);
              setDismissed(false);
            }}
            onKeyDown={onKeyDown}
            placeholder="Search medicines, brands, companies…"
            autoComplete="off"
            className="neo-inset h-11 w-full rounded-lg border border-border pl-10 pr-3 text-base"
          />
        </div>
      </form>
      <div aria-live="polite">
        {error && <p className="mt-1 text-sm text-danger">Search is unavailable right now.</p>}
      </div>
      {results && (
        <div
          id={listId}
          role="listbox"
          aria-label="Search suggestions"
          className="card absolute left-0 right-0 z-20 mt-1 max-h-[70vh] overflow-y-auto p-2 shadow-lg"
        >
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
          {groups.map((items, gi) =>
            items.length ? (
              <div
                key={GROUPS[gi].title}
                role="group"
                aria-label={GROUPS[gi].title}
                className="py-1"
              >
                <p className="px-2 text-xs font-medium uppercase tracking-wide text-muted">
                  {GROUPS[gi].title}
                </p>
                {items.map((it) => {
                  const i = index++;
                  return (
                    <Link
                      key={it.href}
                      id={optionId(i)}
                      role="option"
                      aria-selected={i === active}
                      href={it.href}
                      className={`flex items-center gap-2 rounded-sm px-2 py-2 hover:bg-surface-2 ${
                        i === active ? "bg-surface-2" : ""
                      }`}
                    >
                      <CategoryIcon
                        category={it.category}
                        size={16}
                        className="shrink-0 text-muted"
                      />
                      <span className="min-w-0">
                        <span className="font-medium">{it.main}</span>
                        {it.sub && <span className="ml-2 text-sm text-muted">{it.sub}</span>}
                      </span>
                    </Link>
                  );
                })}
              </div>
            ) : null,
          )}
        </div>
      )}
    </div>
  );
}
