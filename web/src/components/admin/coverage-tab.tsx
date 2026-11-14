"use client";

import { useState } from "react";
import { Button } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { apiSend } from "@/lib/client-api";
import { ListShell, errText, fmt, useList } from "./tabs";

interface Coverage {
  iso2: string;
  name: string;
  mode: string;
  registrations: number;
  products: number;
  sourced_pct: number;
  min_registrations: number;
  min_sourced_pct: number;
  indexable: boolean;
  blockers: string[];
}

/** Which countries search engines may index, and exactly what each one still needs. */
export function CoverageTab() {
  const list = useList<Coverage>("/staff/country-coverage");
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        A country&apos;s pages are kept out of search engines and the sitemap until it has enough
        sourced official listings. Thresholds and the override live on the country in Django admin.
        Visitors can still open every page.
      </p>
      <ListShell list={list} empty="No countries.">
        {(rows) => (
          <ul className="space-y-2">
            {rows.map((c) => (
              <li key={c.iso2} className="card p-3 text-sm">
                <p className="font-medium">
                  {c.name}{" "}
                  <span className={c.indexable ? "text-ok" : "text-warn"}>
                    {c.indexable ? "Indexable" : "Not indexable yet"}
                  </span>
                  {c.mode !== "auto" && (
                    <span className="text-xs text-muted"> (override: {c.mode})</span>
                  )}
                </p>
                <p className="text-xs text-muted">
                  {c.registrations} public registrations (needs {c.min_registrations}) ·{" "}
                  {c.products} products · {c.sourced_pct}% sourced and dated (needs{" "}
                  {c.min_sourced_pct}%)
                </p>
                {c.blockers.length > 0 && (
                  <p className="text-xs">Blocked: {c.blockers.join("; ")}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </ListShell>
    </div>
  );
}

interface Miss {
  id: number;
  query: string;
  example: string;
  count: number;
  last_seen: string;
}

/** Searches that found nothing, most frequent first: this is the import priority list. */
export function MissesTab() {
  const list = useList<Miss>("/staff/search-misses");
  const [error, setError] = useState<string | null>(null);
  async function resolve(id: number) {
    try {
      await apiSend("POST", `/staff/search-misses/${id}/resolve`, { resolved: true });
      list.reload();
    } catch (e) {
      setError(errText(e));
    }
  }
  return (
    <div className="space-y-3">
      {error && <Alert tone="danger">{error}</Alert>}
      <p className="text-sm text-muted">
        What visitors searched for and did not find. Only the normalised text and a counter are
        stored: nothing about who searched. Import data for the top entries, then mark them done; a
        new failed search reopens the entry.
      </p>
      <ListShell list={list} empty="No failed searches recorded.">
        {(rows) => (
          <ul className="space-y-2">
            {rows.map((m) => (
              <li key={m.id} className="card flex items-center justify-between gap-3 p-3 text-sm">
                <span>
                  <span className="font-medium">{m.example || m.query}</span>
                  <span className="block text-xs text-muted">
                    {m.count} search{m.count === 1 ? "" : "es"} · last {fmt(m.last_seen)}
                  </span>
                </span>
                <Button variant="secondary" onClick={() => resolve(m.id)}>
                  Mark done
                </Button>
              </li>
            ))}
          </ul>
        )}
      </ListShell>
    </div>
  );
}
