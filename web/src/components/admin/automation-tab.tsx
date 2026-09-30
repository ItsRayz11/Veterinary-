"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/forms";
import { Alert, DataTable, EmptyState, td, th } from "@/components/ui/primitives";
import { apiFetch, apiSend } from "@/lib/client-api";
import { errText, fmt } from "./tabs";

interface Status {
  can_run: boolean;
  tasks: string[];
  runs: {
    id: number;
    task: string;
    status: string;
    summary: Record<string, unknown>;
    error: string;
    at: string;
  }[];
  broken_sources: {
    id: number;
    title: string;
    url: string;
    error: string;
    failures: number;
    checked_at: string;
  }[];
  feeds: {
    id: number;
    name: string;
    kind: string;
    enabled: boolean;
    last_run_at: string | null;
    last_result: string;
  }[];
}

export function AutomationTab() {
  const [data, setData] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [n, setN] = useState(0);

  useEffect(() => {
    let live = true;
    apiFetch<Status>("/staff/automation")
      .then((d) => live && setData(d))
      .catch(() => live && setError("Could not load automation status."));
    return () => {
      live = false;
    };
  }, [n]);

  async function run(task: string) {
    setBusy(task);
    setError(null);
    try {
      await apiSend("POST", `/staff/automation/run/${task}`, {});
      setN((v) => v + 1);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  if (!data) return error ? <Alert tone="danger">{error}</Alert> : null;
  return (
    <div className="space-y-6">
      {error && <Alert tone="danger">{error}</Alert>}
      <p className="text-sm text-muted">
        Automation only checks links and reads feeds you registered in the Django admin. Feed items
        become pending listings for moderation; nothing is published automatically. Tasks also run
        on a schedule when the scheduler is configured.
      </p>
      {data.can_run && (
        <div className="flex flex-wrap gap-2">
          {data.tasks.map((t) => (
            <Button key={t} variant="secondary" loading={busy === t} onClick={() => run(t)}>
              Run {t} now
            </Button>
          ))}
        </div>
      )}

      <section aria-labelledby="feeds-h" className="space-y-2">
        <h3 id="feeds-h" className="font-semibold">
          Feeds
        </h3>
        {data.feeds.length === 0 ? (
          <EmptyState title="No feeds registered.">
            Register a feed in the Django admin with its licence note; it stays disabled until you
            enable it.
          </EmptyState>
        ) : (
          <DataTable caption="Registered feeds">
            <thead>
              <tr>
                <th className={th}>Feed</th>
                <th className={th}>Status</th>
                <th className={th}>Last run</th>
              </tr>
            </thead>
            <tbody>
              {data.feeds.map((f) => (
                <tr key={f.id}>
                  <td className={td}>
                    {f.name} <span className="text-xs text-muted">({f.kind})</span>
                  </td>
                  <td className={td}>{f.enabled ? "enabled" : "disabled"}</td>
                  <td className={td}>
                    {f.last_run_at ? fmt(f.last_run_at) : "never"}
                    <p className="text-xs text-muted">{f.last_result}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </section>

      <section aria-labelledby="broken-h" className="space-y-2">
        <h3 id="broken-h" className="font-semibold">
          Sources with broken links
        </h3>
        {data.broken_sources.length === 0 ? (
          <EmptyState title="No broken source links recorded." />
        ) : (
          <DataTable caption="Sources whose URL failed the last check">
            <thead>
              <tr>
                <th className={th}>Source</th>
                <th className={th}>Problem</th>
                <th className={th}>Failures in a row</th>
              </tr>
            </thead>
            <tbody>
              {data.broken_sources.map((s) => (
                <tr key={s.id}>
                  <td className={td}>
                    {s.title}
                    <p className="break-all text-xs text-muted">{s.url}</p>
                  </td>
                  <td className={td}>
                    {s.error}
                    <p className="text-xs text-muted">{fmt(s.checked_at)}</p>
                  </td>
                  <td className={td}>{s.failures}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </section>

      <section aria-labelledby="runs-h" className="space-y-2">
        <h3 id="runs-h" className="font-semibold">
          Recent runs
        </h3>
        {data.runs.length === 0 ? (
          <EmptyState title="No runs yet." />
        ) : (
          <DataTable caption="Recent automation runs">
            <thead>
              <tr>
                <th className={th}>When</th>
                <th className={th}>Task</th>
                <th className={th}>Result</th>
              </tr>
            </thead>
            <tbody>
              {data.runs.map((r) => (
                <tr key={r.id}>
                  <td className={td}>{fmt(r.at)}</td>
                  <td className={td}>{r.task}</td>
                  <td className={td}>
                    {r.status}
                    <p className="text-xs text-muted">{r.error || JSON.stringify(r.summary)}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </section>
    </div>
  );
}
