"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Button, Field, Select, TextInput } from "@/components/ui/forms";
import { Alert, DataTable, td, th } from "@/components/ui/primitives";
import { apiFetch, apiSend } from "@/lib/client-api";
import { ListShell, errText, fmt, useList } from "./tabs";

interface Batch {
  id: number;
  country: string;
  file_name: string;
  source: string;
  license_note: string;
  status: string;
  created_at: string;
  counts: Record<string, number>;
}
interface Row {
  id: number;
  row_number: number;
  brand_name: string;
  generic_name: string;
  manufacturer: string;
  registration_number: string;
  status: string;
  message: string;
  generic_match: string | null;
  company_match: string | null;
}
interface Country {
  iso2: string;
  name: string;
}

const TEMPLATE = "brand_name,generic_name,manufacturer,registration_number,registration_status";

export function ImportsTab({ onChanged }: { onChanged: () => void }) {
  const list = useList<Batch>("/staff/imports");
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="space-y-4">
      <ImportForm
        onStaged={(id) => {
          list.reload();
          setOpen(id);
          onChanged();
        }}
      />
      <ListShell list={list} empty="No imports yet.">
        {(rows) => (
          <DataTable caption="Import batches">
            <thead>
              <tr>
                <th className={th}>Batch</th>
                <th className={th}>Source</th>
                <th className={th}>Rows</th>
                <th className={th}>Status</th>
                <th className={th}></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((b) => (
                <tr key={b.id}>
                  <td className={td}>
                    #{b.id} {b.country}
                    <p className="text-xs text-muted">{fmt(b.created_at)}</p>
                  </td>
                  <td className={td}>
                    {b.source}
                    <p className="text-xs text-muted">{b.license_note}</p>
                  </td>
                  <td className={td}>
                    {Object.entries(b.counts)
                      .map(([k, n]) => `${n} ${k}`)
                      .join(", ")}
                  </td>
                  <td className={td}>{b.status}</td>
                  <td className={td}>
                    <button
                      className="text-primary underline"
                      onClick={() => setOpen(open === b.id ? null : b.id)}
                    >
                      {open === b.id ? "Hide" : "Review"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </ListShell>
      {open !== null && (
        <BatchReview
          key={open}
          id={open}
          onChanged={() => {
            list.reload();
            onChanged();
          }}
        />
      )}
    </div>
  );
}

function ImportForm({ onStaged }: { onStaged: (id: number) => void }) {
  const [countries, setCountries] = useState<Country[]>([]);
  const [csv, setCsv] = useState("");
  const [fileName, setFileName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch<Country[]>("/countries")
      .then((c) => setCountries(c ?? []))
      .catch(() => {});
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // currentTarget is null once the handler awaits, so keep the form element now.
    const form = e.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    setError(null);
    try {
      const b = await apiSend<Batch>("POST", "/staff/imports", {
        country: f.get("country"),
        file_name: fileName,
        csv_text: csv,
        source: {
          title: f.get("title"),
          publisher: f.get("publisher"),
          url: f.get("url"),
          license_note: f.get("license_note"),
          source_type: f.get("source_type"),
        },
      });
      setCsv("");
      setFileName("");
      form.reset();
      onStaged(b.id);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="rounded-md border border-border bg-surface p-4">
      <summary className="cursor-pointer font-semibold">Import a product list (CSV)</summary>
      <form onSubmit={submit} className="mt-3 space-y-3" noValidate>
        <p className="text-sm text-muted">
          Columns: <code>{TEMPLATE}</code> (the last two optional). Rows are staged for review;
          nothing becomes public from an import. Only import files whose terms allow it and record
          those terms below.
        </p>
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="imp-country" label="Country">
            <Select id="imp-country" name="country" required defaultValue="">
              <option value="">Choose</option>
              {countries.map((c) => (
                <option key={c.iso2} value={c.iso2}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="imp-type" label="Source type">
            <Select id="imp-type" name="source_type" defaultValue="regulatory">
              <option value="regulatory">Regulatory authority</option>
              <option value="manufacturer">Manufacturer documentation</option>
              <option value="government">Government publication</option>
              <option value="other">Other</option>
            </Select>
          </Field>
          <Field id="imp-title" label="Source title">
            <TextInput id="imp-title" name="title" required />
          </Field>
          <Field id="imp-publisher" label="Publisher">
            <TextInput id="imp-publisher" name="publisher" />
          </Field>
          <Field id="imp-url" label="Source URL">
            <TextInput id="imp-url" name="url" type="url" />
          </Field>
          <Field id="imp-license" label="Licence / terms note (required)">
            <TextInput id="imp-license" name="license_note" required />
          </Field>
        </div>
        <Field id="imp-file" label="CSV file">
          <input
            id="imp-file"
            type="file"
            accept=".csv,text/csv"
            className="text-sm"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) {
                setFileName(file.name);
                setCsv(await file.text());
              }
            }}
          />
        </Field>
        <p className="text-xs text-muted">
          {csv ? `${csv.split("\n").length - 1} lines loaded.` : "No file chosen."}
        </p>
        <Button type="submit" loading={busy} disabled={!csv}>
          Stage for review
        </Button>
      </form>
    </details>
  );
}

function BatchReview({ id, onChanged }: { id: number; onChanged: () => void }) {
  const [data, setData] = useState<(Batch & { rows: Row[] }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [n, setN] = useState(0);
  const [info, setInfo] = useState<string | null>(null);
  const [filter, setFilter] = useState("pending");

  useEffect(() => {
    let live = true;
    apiFetch<Batch & { rows: Row[] }>(`/staff/imports/${id}?status=${filter}`)
      .then((d) => live && setData(d))
      .catch(() => live && setError("Could not load this batch."));
    return () => {
      live = false;
    };
  }, [id, n, filter]);

  async function act(row: Row, decision: "approve" | "reject") {
    let reason = "";
    if (decision === "reject") {
      reason = window.prompt("Reason for rejecting this row?") ?? "";
      if (!reason.trim()) return;
    }
    try {
      await apiSend("POST", `/staff/imports/${id}/rows/${row.id}/${decision}`, { reason });
      setError(null);
      setN((v) => v + 1);
      onChanged();
    } catch (e) {
      setError(errText(e));
    }
  }

  async function approveClean() {
    try {
      const r = await apiSend<{ approved: number; skipped: number; remaining: number }>(
        "POST",
        `/staff/imports/${id}/approve-clean`,
        {},
      );
      setInfo(
        `${r.approved} approved, ${r.skipped} flagged as duplicates or invalid, ${r.remaining} still pending.` +
          (r.remaining > 0 ? " Press the button again to continue." : ""),
      );
      setN((v) => v + 1);
      onChanged();
    } catch (e) {
      setError(errText(e));
    }
  }

  if (!data) return error ? <Alert tone="danger">{error}</Alert> : null;
  return (
    <section aria-label={`Batch ${id} rows`} className="space-y-3">
      <h3 className="font-semibold">Batch #{id}</h3>
      {error && <Alert tone="danger">{error}</Alert>}
      {info && <Alert tone="ok">{info}</Alert>}
      <p className="text-sm text-muted">
        Approving creates unreviewed catalogue records linked to this source. They stay hidden until
        reviewed in the Review queue.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <Button variant="secondary" onClick={approveClean}>
          Approve the next 50 clean pending rows
        </Button>
        <Field id={`filter-${id}`} label="Show rows">
          <Select id={`filter-${id}`} value={filter} onChange={(e) => setFilter(e.target.value)}>
            {["pending", "error", "duplicate", "approved", "rejected"].map((s) => (
              <option key={s} value={s}>
                {s} ({data.counts[s] ?? 0})
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {(data.counts[filter] ?? 0) > data.rows.length && (
        <p className="text-xs text-muted">
          Showing the first {data.rows.length} of {data.counts[filter]}.
        </p>
      )}
      <DataTable caption={`Rows in batch ${id}`}>
        <thead>
          <tr>
            <th className={th}>#</th>
            <th className={th}>Brand</th>
            <th className={th}>Generic (match)</th>
            <th className={th}>Manufacturer (match)</th>
            <th className={th}>Status</th>
            <th className={th}></th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.id}>
              <td className={td}>{r.row_number}</td>
              <td className={td}>
                {r.brand_name}
                {r.registration_number && (
                  <p className="text-xs text-muted">Reg. {r.registration_number}</p>
                )}
              </td>
              <td className={td}>
                {r.generic_name}
                <p className="text-xs text-muted">{r.generic_match ?? "new generic"}</p>
              </td>
              <td className={td}>
                {r.manufacturer}
                <p className="text-xs text-muted">{r.company_match ?? "new company"}</p>
              </td>
              <td className={td}>
                {r.status}
                {r.message && <p className="text-xs text-muted">{r.message}</p>}
              </td>
              <td className={`${td} space-x-2 whitespace-nowrap`}>
                {r.status === "pending" && (
                  <button className="text-primary underline" onClick={() => act(r, "approve")}>
                    Approve
                  </button>
                )}
                {["pending", "duplicate", "error"].includes(r.status) && (
                  <button className="text-primary underline" onClick={() => act(r, "reject")}>
                    Reject
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </section>
  );
}
