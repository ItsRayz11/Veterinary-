"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Brand } from "@/lib/api";
import { td, th } from "@/components/ui/primitives";
import { StatusBadge } from "@/components/ui/status-badge";

const PAGE_SIZE = 50;

/**
 * Catalogue table with live filtering and paging. It only re-presents the records it is given,
 * and shows the "imported, not reviewed" badge on every unreviewed row so filtering or paging can
 * never separate a record from its review state.
 */
export function ProductTable({
  products,
  caption,
  showManufacturer = true,
  showCountries = false,
}: {
  products: Brand[];
  caption: string;
  showManufacturer?: boolean;
  showCountries?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return products;
    return products.filter((p) =>
      [p.brand_name, p.generic_name, p.manufacturer.name].some((v) => v.toLowerCase().includes(q)),
    );
  }, [products, query]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const rows = filtered.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="product-filter" className="sr-only">
          Filter by brand, generic or manufacturer
        </label>
        <input
          id="product-filter"
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(0);
          }}
          placeholder="Filter by brand, generic or manufacturer"
          className="neo-inset min-h-11 w-full max-w-md rounded-lg border border-border px-3 text-sm focus:border-primary"
        />
        <p className="text-sm text-muted" aria-live="polite">
          {filtered.length === products.length
            ? `${products.length} products`
            : `${filtered.length} of ${products.length} products`}
        </p>
      </div>

      <div className="card max-h-[70vh] overflow-auto">
        <table className="data-table w-full min-w-[32rem] border-collapse text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              <th scope="col" className={th}>
                Brand
              </th>
              <th scope="col" className={th}>
                Generic
              </th>
              {showManufacturer && (
                <th scope="col" className={th}>
                  Manufacturer
                </th>
              )}
              {showCountries && (
                <th scope="col" className={th}>
                  Countries
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td className={td} colSpan={2 + Number(showManufacturer) + Number(showCountries)}>
                  No products match &ldquo;{query}&rdquo;.
                </td>
              </tr>
            )}
            {rows.map((p) => (
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
                {showManufacturer && (
                  <td className={td}>
                    <Link
                      className="text-primary underline"
                      href={`/companies/${p.manufacturer.slug}`}
                    >
                      {p.manufacturer.name}
                    </Link>
                  </td>
                )}
                {showCountries && <td className={td}>{p.countries.join(", ") || "–"}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <nav aria-label="Pagination" className="flex items-center justify-between text-sm">
          <button
            type="button"
            className="neo min-h-11 rounded-lg px-4 disabled:opacity-50"
            disabled={current === 0}
            onClick={() => setPage(current - 1)}
          >
            Previous
          </button>
          <span className="text-muted">
            Page {current + 1} of {pages}
          </span>
          <button
            type="button"
            className="neo min-h-11 rounded-lg px-4 disabled:opacity-50"
            disabled={current >= pages - 1}
            onClick={() => setPage(current + 1)}
          >
            Next
          </button>
        </nav>
      )}
    </div>
  );
}
