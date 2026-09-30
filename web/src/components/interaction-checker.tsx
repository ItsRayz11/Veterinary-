"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, EmptyState } from "@/components/ui/primitives";
import { Field, TextInput } from "@/components/ui/forms";
import { apiFetch } from "@/lib/client-api";

interface Drug {
  name: string;
  slug: string;
}
interface Result {
  checked: Drug[];
  unresolved: string[];
  interactions: {
    a: Drug;
    b: Drug;
    severity: string;
    description: string;
    development_data: boolean;
    sources: { id: number; title: string; url: string }[];
  }[];
  note: string;
}

const TONE: Record<string, "danger" | "warn" | "info"> = {
  contraindicated: "danger",
  major: "danger",
  moderate: "warn",
  minor: "info",
};

export function InteractionChecker() {
  const [q, setQ] = useState("");
  const [options, setOptions] = useState<Drug[]>([]);
  const [chosen, setChosen] = useState<Drug[]>([]);
  // Each answer remembers which selection it was computed for, so a result (especially the
  // reassuring "nothing recorded") is never shown next to a different list of drugs.
  const [result, setResult] = useState<{ key: string; data: Result } | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const key = chosen
    .map((c) => c.slug)
    .sort()
    .join(",");

  useEffect(() => {
    if (q.trim().length < 2) return;
    let live = true;
    const t = setTimeout(() => {
      apiFetch<{ generics: Drug[] }>(`/search?q=${encodeURIComponent(q)}`)
        .then((d) => live && setOptions(d?.generics ?? []))
        .catch(() => {});
    }, 200);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [q]);

  useEffect(() => {
    if (chosen.length < 2) return;
    let live = true;
    apiFetch<Result>(`/interactions/check?generics=${key}`)
      .then((r) => {
        if (!live) return;
        if (r) {
          setResult({ key, data: r });
          setFailed(null);
        } else {
          setFailed(key); // 401/403: not an answer, so never leave "Checking…" on screen
        }
      })
      .catch(() => live && setFailed(key));
    return () => {
      live = false;
    };
  }, [chosen.length, key]);

  const shown =
    q.trim().length >= 2 ? options.filter((o) => !chosen.some((c) => c.slug === o.slug)) : [];
  const enough = chosen.length >= 2;
  const active = enough && result?.key === key ? result.data : null;
  const loading = enough && !active && failed !== key;

  return (
    <div className="space-y-4">
      <Field id="drug" label="Add a drug" hint="Search by generic name; choose at least two.">
        <TextInput id="drug" value={q} autoComplete="off" onChange={(e) => setQ(e.target.value)} />
      </Field>
      {shown.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Search results">
          {shown.map((o) => (
            <li key={o.slug}>
              <button
                type="button"
                className="min-h-11 rounded-full border border-border bg-surface px-3 text-sm hover:border-primary"
                onClick={() => {
                  setChosen((c) => (c.length >= 8 ? c : [...c, o]));
                  setQ("");
                  setOptions([]);
                }}
              >
                + {o.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      {chosen.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Selected drugs">
          {chosen.map((c) => (
            <li
              key={c.slug}
              className="flex items-center gap-2 rounded-full bg-surface-2 px-3 py-1 text-sm"
            >
              {c.name}
              <button
                type="button"
                aria-label={`Remove ${c.name}`}
                className="text-muted hover:text-text"
                onClick={() => setChosen((list) => list.filter((x) => x.slug !== c.slug))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      {enough && failed === key && <Alert tone="danger">Could not check interactions.</Alert>}
      <div aria-live="polite" className="space-y-3">
        {!enough && <p className="text-sm text-muted">Choose at least two drugs.</p>}
        {loading && <p className="text-sm text-muted">Checking…</p>}
        {active && active.interactions.length === 0 && (
          <EmptyState title="No reviewed interaction is recorded for these drugs.">
            {active.note}
          </EmptyState>
        )}
        {active?.interactions.map((i) => (
          <Alert
            key={`${i.a.slug}-${i.b.slug}`}
            tone={TONE[i.severity] ?? "info"}
            title={`${i.a.name} + ${i.b.name}: ${i.severity}`}
          >
            <p>{i.description}</p>
            {i.development_data && <p className="text-xs">Development data, not verified.</p>}
            {i.sources.length > 0 && (
              <p className="mt-1 text-xs">
                Sources:{" "}
                {i.sources.map((s) => (
                  <a
                    key={s.id}
                    className="underline"
                    href={s.url}
                    rel="noopener noreferrer nofollow"
                    target="_blank"
                  >
                    {s.title}{" "}
                  </a>
                ))}
              </p>
            )}
          </Alert>
        ))}
        {active && active.interactions.length > 0 && (
          <p className="text-xs text-muted">{active.note}</p>
        )}
        {active && active.unresolved.length > 0 && (
          <p className="text-xs text-muted">Not found: {active.unresolved.join(", ")}</p>
        )}
      </div>
      <p className="text-sm">
        <Link className="text-primary underline" href="/search">
          Search drugs
        </Link>
      </p>
    </div>
  );
}
