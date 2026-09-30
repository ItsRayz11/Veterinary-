"use client";

import { useState } from "react";
import { Button } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { apiSend } from "@/lib/client-api";
import { ListShell, errText, fmt, useList } from "./tabs";

interface Row {
  id: number;
  message: string;
  stack: string;
  path: string;
  count: number;
  first_seen: string;
  last_seen: string;
  release: string;
}

export function ErrorsTab() {
  const list = useList<Row>("/staff/errors");
  const [error, setError] = useState<string | null>(null);

  async function resolve(id: number) {
    try {
      await apiSend("POST", `/staff/errors/${id}/resolve`, {});
      list.reload();
    } catch (e) {
      setError(errText(e));
    }
  }

  return (
    <div className="space-y-3">
      {error && <Alert tone="danger">{error}</Alert>}
      <p className="text-sm text-muted">
        Errors reported by visitors&apos; browsers, grouped by cause. Emails, tokens and query
        strings are removed before anything is stored. An error that comes back after being resolved
        reopens.
      </p>
      <ListShell list={list} empty="No open errors reported.">
        {(rows) => (
          <ul className="space-y-2">
            {rows.map((r) => (
              <li key={r.id} className="rounded-md border border-border bg-surface p-3 text-sm">
                <p className="font-medium">{r.message}</p>
                <p className="text-xs text-muted">
                  {r.count} time{r.count === 1 ? "" : "s"} · {r.path || "unknown page"} · last{" "}
                  {fmt(r.last_seen)}
                  {r.release && ` · release ${r.release}`}
                </p>
                {r.stack && (
                  <details className="mt-1">
                    <summary className="cursor-pointer text-xs">Stack</summary>
                    <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-xs">
                      {r.stack}
                    </pre>
                  </details>
                )}
                <Button variant="secondary" className="mt-2" onClick={() => resolve(r.id)}>
                  Mark resolved
                </Button>
              </li>
            ))}
          </ul>
        )}
      </ListShell>
    </div>
  );
}
