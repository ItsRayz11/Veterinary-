"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/forms";
import { apiFetch } from "@/lib/client-api";
import type { SectionKey } from "./nav";
import type { Summary } from "./admin-panel";
import { fmt } from "./tabs";

interface Auto {
  runs: { id: number; task: string; status: string; at: string; error: string }[];
  broken_sources: { id: number }[];
  data_sources: { update_available: boolean; reachable: boolean | null }[];
}

function Stat({
  label,
  value,
  go,
  tone,
  hint,
}: {
  label: string;
  value: number | string;
  go: () => void;
  tone?: "warn" | "danger";
  hint?: string;
}) {
  const color =
    tone === "danger" ? "text-danger" : tone === "warn" ? "text-warn" : "text-foreground";
  return (
    <button
      type="button"
      onClick={go}
      className="card min-w-0 p-4 text-left transition hover:border-primary focus-visible:outline-2"
    >
      <span className="block text-xs text-muted">{label}</span>
      <span className={`mt-1 block text-2xl font-semibold ${color}`}>{value}</span>
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </button>
  );
}

/** Real counts only; each tile opens the exact list it counts. */
export function Overview({
  summary,
  isModerator,
  go,
}: {
  summary: Summary | null;
  isModerator: boolean;
  go: (k: SectionKey) => void;
}) {
  const [auto, setAuto] = useState<Auto | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    apiFetch<Auto>("/staff/automation")
      .then((a) => live && setAuto(a ?? null))
      .catch(() => live && setAuto(null));
    return () => {
      live = false;
    };
  }, []);

  if (!summary) return <Skeleton className="h-32 w-full" />;
  const queueTotal = Object.values(summary.review_queue).reduce((a, b) => a + b, 0);
  const failedRuns =
    auto?.runs.filter((r) => r.status !== "ok" && r.status !== "running").length ?? 0;
  const updates = auto?.data_sources.filter((d) => d.update_available).length ?? 0;
  const unreachable = auto?.data_sources.filter((d) => d.reachable === false).length ?? 0;

  return (
    <div className="space-y-5">
      <section aria-label="Waiting for a person">
        <h2 className="mb-2 text-sm font-semibold">Waiting for a person</h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Review queue" value={queueTotal.toLocaleString()} go={() => go("queue")} />
          {isModerator && (
            <>
              <Stat
                label="Jobs & scholarships"
                value={summary.listings_pending ?? 0}
                go={() => go("listings")}
              />
              <Stat
                label="Price submissions"
                value={summary.price_submissions_pending}
                go={() => go("prices")}
              />
              <Stat
                label="Question reports"
                value={summary.question_reports_open}
                go={() => go("reports")}
              />
            </>
          )}
        </div>
      </section>

      <section aria-label="Sources and automation">
        <h2 className="mb-2 text-sm font-semibold">Sources and automation</h2>
        {auto === undefined ? (
          <Skeleton className="h-20 w-full" />
        ) : auto === null ? (
          <p className="text-sm text-muted">Automation status is not available to your account.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat
              label="Source updates available"
              value={updates}
              go={() => go("imports")}
              tone={updates ? "warn" : undefined}
            />
            <Stat
              label="Unreachable sources"
              value={unreachable + auto.broken_sources.length}
              go={() => go("automation")}
              tone={unreachable + auto.broken_sources.length ? "danger" : undefined}
            />
            <Stat
              label="Recent runs that failed"
              value={failedRuns}
              go={() => go("errors")}
              tone={failedRuns ? "danger" : undefined}
              hint={`of last ${auto.runs.length}`}
            />
            <Stat
              label="Last run"
              value={auto.runs[0] ? auto.runs[0].task : "none"}
              go={() => go("automation")}
              hint={auto.runs[0] ? `${auto.runs[0].status}, ${fmt(auto.runs[0].at)}` : undefined}
            />
          </div>
        )}
      </section>

      <section aria-label="Queue by record type">
        <h2 className="mb-2 text-sm font-semibold">Queue by record type</h2>
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(summary.review_queue).map(([k, n]) => (
            <li key={k} className="card flex items-center justify-between px-3 py-2 text-sm">
              <span className="truncate">{k}</span>
              <span className="font-medium">{n.toLocaleString()}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
