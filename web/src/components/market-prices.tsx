"use client";

import { useEffect, useState } from "react";
import { Field, Select, Skeleton } from "@/components/ui/forms";
import { DataTable, EmptyState, td, th } from "@/components/ui/primitives";
import { apiFetch } from "@/lib/client-api";

interface Comparison {
  packs: {
    pack: string;
    unit: string;
    rows: {
      country: string;
      price_type: string;
      amount: string;
      currency: string;
      per_unit: string;
      observed_on: string;
      source: { title: string; url: string } | null;
      converted: string | null;
      converted_currency: string | null;
      fx_as_of: string | null;
    }[];
  }[];
  note: string;
  currencies: string[];
}
interface Offers {
  results: {
    retailer: string;
    kind: string;
    city: string;
    country: string;
    pack: string;
    amount: string;
    currency: string;
    price_date: string;
    stock: string;
    stock_label: string;
    stock_checked_at: string | null;
    listing_url: string;
    note: string;
  }[];
  note: string;
}

/** Local-currency prices by country per pack, with optional indicative conversion. */
export function PriceComparison({ slug }: { slug: string }) {
  const [currency, setCurrency] = useState("");
  const [country, setCountry] = useState("");
  const [data, setData] = useState<Comparison | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    apiFetch<Comparison>(
      `/products/${slug}/price-comparison/${currency ? `?currency=${currency}` : ""}`,
    )
      .then((d) => live && setData(d))
      .catch(() => live && setData(null));
    return () => {
      live = false;
    };
  }, [slug, currency]);

  if (data === undefined) return <Skeleton className="h-24 w-full" />;
  if (!data || data.packs.length === 0)
    return <EmptyState title="No published prices to compare yet." />;
  const countries = [...new Set(data.packs.flatMap((p) => p.rows.map((r) => r.country)))].sort();
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field id="cmp-country" label="Country">
          <Select id="cmp-country" value={country} onChange={(e) => setCountry(e.target.value)}>
            <option value="">All countries</option>
            {countries.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </Select>
        </Field>
        <Field
          id="cmp-ccy"
          label="Show indicative conversion in"
          hint={data.currencies.length ? undefined : "No exchange rates entered yet."}
        >
          <Select id="cmp-ccy" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            <option value="">Local currency only</option>
            {data.currencies.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </Select>
        </Field>
      </div>
      {data.packs.map((p) => {
        const rows = p.rows.filter((r) => !country || r.country === country);
        if (!rows.length) return null;
        return (
          <DataTable key={p.pack} caption={`Prices for ${p.pack}`}>
            <thead>
              <tr>
                {["Country", "Type", "Price", `Per ${p.unit}`, "Indicative", "Date"].map((h) => (
                  <th key={h} scope="col" className={th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.country}-${r.price_type}`}>
                  <th scope="row" className={td}>
                    {r.country}
                  </th>
                  <td className={td}>{r.price_type.replaceAll("_", " ")}</td>
                  <td className={td}>
                    {r.currency} {r.amount}
                  </td>
                  <td className={td}>
                    {r.currency} {r.per_unit}
                  </td>
                  <td className={td}>
                    {r.converted
                      ? `≈ ${r.converted_currency} ${r.converted} (rate ${r.fx_as_of ? new Date(r.fx_as_of).toLocaleDateString() : "n/a"})`
                      : currency
                        ? "No rate"
                        : ""}
                  </td>
                  <td className={td}>
                    {new Date(r.observed_on).toLocaleDateString()}
                    {r.source && (
                      <>
                        {" "}
                        <a
                          href={r.source.url}
                          rel="noopener noreferrer nofollow"
                          target="_blank"
                          className="text-primary underline"
                        >
                          source
                        </a>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        );
      })}
      <p className="text-xs text-muted">{data.note}</p>
    </div>
  );
}

/** Participating retailers. Stock is only shown when recently confirmed; otherwise Unknown. */
export function RetailerOffers({ slug }: { slug: string }) {
  const [country, setCountry] = useState("");
  const [data, setData] = useState<Offers | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    apiFetch<Offers>(`/products/${slug}/offers/`)
      .then((d) => live && setData(d))
      .catch(() => live && setData(null));
    return () => {
      live = false;
    };
  }, [slug]);
  if (data === undefined) return <Skeleton className="h-16 w-full" />;
  if (!data || data.results.length === 0)
    return (
      <EmptyState title="No participating retailers have listed this product yet.">
        Availability is unknown. Retailers can join through VetRef staff.
      </EmptyState>
    );
  const where = [...new Set(data.results.map((o) => o.country))].sort();
  const shown = data.results.filter((o) => !country || o.country === country);
  return (
    <div className="space-y-2">
      {where.length > 1 && (
        <Field id="offer-country" label="Country">
          <Select id="offer-country" value={country} onChange={(e) => setCountry(e.target.value)}>
            <option value="">All countries</option>
            {where.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </Select>
        </Field>
      )}
      <DataTable caption="Participating retailers">
        <thead>
          <tr>
            {["Retailer", "Pack", "Price", "Stock", "Price date"].map((h) => (
              <th key={h} scope="col" className={th}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((o, i) => (
            <tr key={i}>
              <th scope="row" className={td}>
                {o.listing_url ? (
                  <a
                    href={o.listing_url}
                    rel="noopener noreferrer nofollow"
                    target="_blank"
                    className="text-primary underline"
                  >
                    {o.retailer}
                  </a>
                ) : (
                  o.retailer
                )}
                <p className="text-xs font-normal text-muted">
                  {o.kind}
                  {o.city && ` · ${o.city}`}
                </p>
              </th>
              <td className={td}>{o.pack}</td>
              <td className={td}>
                {o.currency} {o.amount}
                {o.note && <p className="text-xs text-muted">{o.note}</p>}
              </td>
              <td className={td}>
                {o.stock_label}
                {o.stock_checked_at && o.stock !== "unknown" && (
                  <p className="text-xs text-muted">
                    Last checked {new Date(o.stock_checked_at).toLocaleDateString()}
                  </p>
                )}
              </td>
              <td className={td}>{new Date(o.price_date).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <p className="text-xs text-muted">{data.note}</p>
    </div>
  );
}
