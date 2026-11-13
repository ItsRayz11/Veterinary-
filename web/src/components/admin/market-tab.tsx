"use client";

import { useState } from "react";
import { Field, TextInput } from "@/components/ui/forms";
import { apiFetch } from "@/lib/client-api";
import { CrudSection, type FieldDef } from "./crud-section";
import { fmt, useList } from "./tabs";

interface Retailer extends Record<string, unknown> {
  id: number;
  name: string;
  country_iso2: string;
  kind: string;
  status: string;
  city: string;
}
interface Offer extends Record<string, unknown> {
  id: number;
  retailer_name: string;
  pack_label: string;
  amount: string;
  currency: string;
  stock_state: string;
  effective_stock: string;
  stock_checked_at: string | null;
  status: string;
  verified: boolean;
}
interface Fx extends Record<string, unknown> {
  id: number;
  currency: string;
  usd_per_unit: string;
  as_of: string;
  source_note: string;
}

const STATUS = [
  ["pending", "Pending review"],
  ["approved", "Approved"],
  ["paused", "Paused"],
  ["removed", "Removed"],
] as const;

function PackFinder() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ id: number; label: string }[]>([]);
  return (
    <div className="space-y-1">
      <Field id="pack-find" label="Pack finder" hint="Type 2+ letters of a brand name">
        <TextInput
          id="pack-find"
          type="search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            if (e.target.value.trim().length >= 2)
              apiFetch<{ results: { id: number; label: string }[] }>(
                `/staff/lookups/packs/?q=${encodeURIComponent(e.target.value.trim())}`,
              ).then((r) => setHits(r?.results ?? []));
            else setHits([]);
          }}
        />
      </Field>
      {hits.length > 0 && (
        <ul className="text-xs">
          {hits.map((h) => (
            <li key={h.id}>
              <span className="font-mono">{h.id}</span> {h.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function MarketTab({ admin }: { admin: boolean }) {
  const retailers = useList<Retailer>("/staff/retailers/");
  const countries = useList<{ id: number; iso2: string; name: string }>(
    "/staff/lookups/countries/",
  );
  const retailerOptions = (retailers.rows ?? []).map(
    (r) => [String(r.id), r.name] as [string, string],
  );
  const countryOptions = (countries.rows ?? []).map(
    (c) => [String(c.id), `${c.name} (${c.iso2})`] as [string, string],
  );
  const retailerFields: FieldDef[] = [
    { name: "name", label: "Retailer name" },
    { name: "country", label: "Country", type: "select" },
    { name: "city", label: "City" },
    {
      name: "kind",
      label: "Type",
      type: "select",
      options: [
        ["online", "Online shop"],
        ["offline", "Physical store"],
        ["both", "Online and physical"],
      ],
    },
    { name: "website", label: "Website", type: "url" },
    { name: "status", label: "Status", type: "select", options: STATUS },
    { name: "integrates_stock", label: "Retailer syncs stock itself", type: "checkbox" },
  ];
  return (
    <div className="space-y-8">
      <section className="space-y-2" aria-label="Retailers">
        <h3 className="font-semibold">Retailers</h3>
        <CrudSection<Retailer>
          path="/staff/retailers"
          caption="Retailers"
          empty="No retailers yet."
          newLabel="Add a retailer"
          dynamicOptions={{ country: countryOptions }}
          defaults={{ kind: "online", status: "pending" }}
          fields={retailerFields}
          columns={[
            { header: "Retailer", render: (r) => r.name },
            { header: "Where", render: (r) => [r.city, r.country_iso2].filter(Boolean).join(", ") },
            { header: "Type", render: (r) => r.kind },
            { header: "Status", render: (r) => r.status },
          ]}
        />
      </section>

      <section className="space-y-2" aria-label="Offers">
        <h3 className="font-semibold">Offers and stock</h3>
        <p className="text-sm text-muted">
          Only approved and verified offers from approved retailers are public. Stock is shown only
          if checked within 14 days; otherwise it reads Unknown. Never set a stock state you have
          not confirmed with the retailer.
        </p>
        <PackFinder />
        <CrudSection<Offer>
          path="/staff/offers"
          caption="Retailer offers"
          empty="No offers yet."
          newLabel="Add an offer"
          dynamicOptions={{ retailer: retailerOptions }}
          defaults={{ stock_state: "unknown", status: "pending", currency: "" }}
          fields={[
            { name: "retailer", label: "Retailer", type: "select" },
            {
              name: "pack",
              label: "Product pack ID",
              type: "number",
              hint: "Find it by brand name in the pack finder below",
            },
            { name: "amount", label: "Price", type: "number" },
            { name: "currency", label: "Currency (ISO 4217)" },
            { name: "price_observed_on", label: "Price date (YYYY-MM-DD)" },
            {
              name: "stock_state",
              label: "Stock",
              type: "select",
              options: [
                ["unknown", "Unknown"],
                ["in_stock", "In stock"],
                ["limited", "Limited"],
                ["out_of_stock", "Out of stock"],
              ],
            },
            { name: "stock_checked_at", label: "Stock last checked (ISO date-time)" },
            { name: "listing_url", label: "Listing link (https)", type: "url" },
            { name: "tax_shipping_note", label: "Tax / shipping note" },
            { name: "status", label: "Status", type: "select", options: STATUS },
            { name: "verified", label: "Verified against the listing", type: "checkbox" },
          ]}
          columns={[
            {
              header: "Offer",
              render: (r) => (
                <>
                  {r.retailer_name}
                  <p className="text-xs text-muted">{r.pack_label}</p>
                </>
              ),
            },
            { header: "Price", render: (r) => `${r.currency} ${r.amount}` },
            {
              header: "Stock",
              render: (r) => (
                <>
                  {r.effective_stock}
                  {r.stock_checked_at && (
                    <p className="text-xs text-muted">checked {fmt(r.stock_checked_at)}</p>
                  )}
                </>
              ),
            },
            { header: "State", render: (r) => `${r.status}${r.verified ? ", verified" : ""}` },
          ]}
        />
      </section>

      {admin && (
        <section className="space-y-2" aria-label="Exchange rates">
          <h3 className="font-semibold">Indicative exchange rates</h3>
          <p className="text-sm text-muted">
            Entered by an admin from a source you note here. VetRef never fetches or invents rates;
            without a rate, no conversion is shown.
          </p>
          <CrudSection<Fx>
            path="/staff/fx-rates"
            caption="Exchange rates"
            empty="No rates entered. Prices show in local currency only."
            newLabel="Add a rate"
            fields={[
              { name: "currency", label: "Currency (ISO 4217)" },
              { name: "usd_per_unit", label: "USD per 1 unit of this currency", type: "number" },
              { name: "as_of", label: "As of (ISO date-time)" },
              { name: "source_note", label: "Source of the rate" },
            ]}
            columns={[
              { header: "Currency", render: (r) => r.currency },
              { header: "USD per unit", render: (r) => r.usd_per_unit },
              { header: "As of", render: (r) => fmt(r.as_of) },
              { header: "Source", render: (r) => r.source_note },
            ]}
          />
        </section>
      )}
    </div>
  );
}
