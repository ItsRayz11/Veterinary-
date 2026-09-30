"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/primitives";
import { Button, Field, Select, TextInput } from "@/components/ui/forms";
import { ClientApiError, apiFetch, apiSend } from "@/lib/client-api";
import { useUser } from "@/lib/use-user";
import type { PriceRow } from "@/lib/api";

const PRICE_TYPES = [
  ["retail", "Retail price"],
  ["distributor", "Distributor price"],
  ["manufacturer_suggested", "Manufacturer suggested price"],
] as const;

interface Choice {
  id: number;
  label: string;
}
interface CountryRow {
  iso2: string;
  name: string;
  currency: string;
}

/** Suggest a price or report a wrong one. Everything goes to moderation; nothing is shown until approved. */
export function PriceSubmitForm({ slug, current }: { slug: string; current: PriceRow[] }) {
  const user = useUser();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"new_price" | "report_incorrect">("new_price");
  const [packs, setPacks] = useState<Choice[]>([]);
  const [countries, setCountries] = useState<CountryRow[]>([]);
  const [pack, setPack] = useState("");
  const [error, setError] = useState<ClientApiError | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || packs.length) return;
    Promise.all([
      apiFetch<Choice[]>(`/products/${slug}/packs`),
      apiFetch<CountryRow[]>("/countries"),
    ])
      .then(([p, c]) => {
        setPacks(p ?? []);
        setCountries(c ?? []);
      })
      .catch(() => setError(new ClientApiError("Could not load the form options.", 0)));
  }, [open, packs.length, slug]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const payload: Record<string, unknown> = { kind };
    for (const [k, v] of f.entries()) if (typeof v === "string" && v !== "") payload[k] = v;
    if (payload.pack) payload.pack = Number(payload.pack);
    if (payload.target) payload.target = Number(payload.target);
    setBusy(true);
    setError(null);
    try {
      await apiSend("POST", "/prices/submissions", payload);
      setDone(true);
    } catch (err) {
      setError(
        err instanceof ClientApiError ? err : new ClientApiError("Something went wrong.", 0),
      );
    } finally {
      setBusy(false);
    }
  }

  if (done)
    return (
      <Alert tone="ok" title="Thank you">
        Your submission is waiting for moderator review. It is not shown publicly until approved.
      </Alert>
    );

  if (!open)
    return (
      <button
        type="button"
        className="text-sm text-primary underline"
        onClick={() => setOpen(true)}
      >
        Suggest a price or report a wrong one
      </button>
    );

  if (user === null)
    return (
      <Alert tone="info">
        <Link href={`/login?next=/products/${slug}`} className="underline">
          Sign in
        </Link>{" "}
        to suggest or report a price.
      </Alert>
    );

  const fe = error?.fields ?? {};
  const targets = current.filter((r) => String(r.pack_id) === pack);
  return (
    <form
      onSubmit={submit}
      className="space-y-3 rounded-md border border-border bg-surface p-4"
      noValidate
    >
      <h3 className="font-semibold">Suggest or report a price</h3>
      {error && Object.keys(fe).length === 0 && <Alert tone="danger">{error.message}</Alert>}
      <fieldset className="flex gap-4 text-sm">
        <legend className="sr-only">Type of submission</legend>
        {(
          [
            ["new_price", "New price"],
            ["report_incorrect", "Report an incorrect price"],
          ] as const
        ).map(([v, l]) => (
          <label key={v} className="flex min-h-11 items-center gap-2">
            <input type="radio" checked={kind === v} onChange={() => setKind(v)} /> {l}
          </label>
        ))}
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field id="pack" label="Pack" error={fe.pack}>
          <Select
            id="pack"
            name="pack"
            required
            value={pack}
            onChange={(e) => setPack(e.target.value)}
            error={fe.pack}
          >
            <option value="">Choose a pack</option>
            {packs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field id="country" label="Country" error={fe.country}>
          <Select id="country" name="country" required error={fe.country} defaultValue="">
            <option value="">Choose a country</option>
            {countries.map((c) => (
              <option key={c.iso2} value={c.iso2}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field id="region" label="Region (optional)">
          <TextInput id="region" name="region" maxLength={100} />
        </Field>
        <Field id="city" label="City (optional)">
          <TextInput id="city" name="city" maxLength={100} />
        </Field>
        {kind === "new_price" ? (
          <>
            <Field id="price_type" label="Price type" error={fe.price_type}>
              <Select
                id="price_type"
                name="price_type"
                required
                error={fe.price_type}
                defaultValue=""
              >
                <option value="">Choose</option>
                {PRICE_TYPES.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="amount" label="Price" error={fe.amount} hint="In the country's currency">
              <TextInput
                id="amount"
                name="amount"
                inputMode="decimal"
                required
                error={fe.amount}
                hint="In the country's currency"
              />
            </Field>
          </>
        ) : (
          <Field id="target" label="Price you are reporting" error={fe.target}>
            <Select id="target" name="target" required error={fe.target} defaultValue="">
              <option value="">{pack ? "Choose the price" : "Choose a pack first"}</option>
              {targets.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.currency} {r.amount} ({r.price_type.replace("_", " ")})
                </option>
              ))}
            </Select>
          </Field>
        )}
      </div>
      <Field id="note" label="Note (optional)" error={fe.note}>
        <TextInput id="note" name="note" maxLength={500} error={fe.note} />
      </Field>
      <Field id="evidence_url" label="Evidence link (optional)" error={fe.evidence_url}>
        <TextInput id="evidence_url" name="evidence_url" type="url" error={fe.evidence_url} />
      </Field>
      <div className="flex gap-2">
        <Button type="submit" loading={busy}>
          Send for review
        </Button>
        <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
