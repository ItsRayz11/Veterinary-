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

interface Suggestion {
  slug: string;
  name: string;
  via: "spelling" | "ai";
}

interface Miss {
  id: number;
  query: string;
  example: string;
  count: number;
  last_seen: string;
  suggestions: Suggestion[];
}

/**
 * Searches that found nothing, most frequent first: the import priority list. Where a listed
 * generic matches the spelling (or the AI names one that is listed), one click adds the visitor's
 * spelling as a synonym, so the same search finds it next time. Nothing is added without a click.
 */
export function MissesTab() {
  const list = useList<Miss>("/staff/search-misses");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [ai, setAi] = useState<Record<number, { suggestions: Suggestion[]; note: string }>>({});

  async function run(id: number, action: () => Promise<unknown>) {
    setBusy(id);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }
  const resolve = (id: number) =>
    run(id, async () => {
      await apiSend("POST", `/staff/search-misses/${id}/resolve`, { resolved: true });
      list.reload();
    });
  const accept = (id: number, slug: string) =>
    run(id, async () => {
      await apiSend("POST", `/staff/search-misses/${id}/accept`, { generic: slug });
      list.reload();
    });
  const askAi = (id: number) =>
    run(id, async () => {
      const out = await apiSend<{ suggestions: Suggestion[]; note: string }>(
        "POST",
        `/staff/search-misses/${id}/ai-suggest`,
      );
      if (out) setAi((m) => ({ ...m, [id]: out }));
    });

  return (
    <div className="space-y-3">
      {error && <Alert tone="danger">{error}</Alert>}
      <p className="text-sm text-muted">
        What visitors searched for and did not find. Only the normalised text and a counter are
        stored: nothing about who searched. Accept a suggestion to add the spelling as a synonym,
        import data for the rest, or mark an entry done. A new failed search reopens it.
      </p>
      <ListShell list={list} empty="No failed searches recorded.">
        {(rows) => (
          <ul className="space-y-2">
            {rows.map((m) => {
              const fromAi = ai[m.id];
              const suggestions = [...m.suggestions, ...(fromAi?.suggestions ?? [])];
              return (
                <li key={m.id} className="card space-y-2 p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="min-w-0">
                      <span className="font-medium">{m.example || m.query}</span>
                      <span className="block text-xs text-muted">
                        {m.count} search{m.count === 1 ? "" : "es"} · last {fmt(m.last_seen)}
                      </span>
                    </span>
                    <Button
                      variant="secondary"
                      disabled={busy === m.id}
                      onClick={() => resolve(m.id)}
                    >
                      Mark done
                    </Button>
                  </div>
                  {suggestions.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-2">
                      {suggestions.map((sg) => (
                        <Button
                          key={`${sg.via}-${sg.slug}`}
                          variant="secondary"
                          disabled={busy === m.id}
                          onClick={() => accept(m.id, sg.slug)}
                        >
                          Add as synonym of {sg.name}
                          <span className="text-xs text-muted">
                            {sg.via === "ai" ? "AI suggested" : "similar spelling"}
                          </span>
                        </Button>
                      ))}
                    </div>
                  ) : fromAi ? (
                    <p className="text-xs text-muted">{fromAi.note || "No suggestion."}</p>
                  ) : (
                    <Button variant="secondary" loading={busy === m.id} onClick={() => askAi(m.id)}>
                      Ask AI which drug this is
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </ListShell>
    </div>
  );
}
