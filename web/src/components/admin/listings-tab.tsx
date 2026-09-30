"use client";

import { useState } from "react";
import { Button } from "@/components/ui/forms";
import { Alert, DataTable, td, th } from "@/components/ui/primitives";
import { apiSend } from "@/lib/client-api";
import { ListShell, errText, fmt, useList } from "./tabs";

interface Row {
  id: number;
  kind: "jobs" | "scholarships";
  title: string;
  organization: string;
  country_name: string | null;
  description: string;
  apply_url: string;
  closes_on: string | null;
  submitted_by: string;
  created_at: string;
}

export function ListingsTab({ onChanged }: { onChanged: () => void }) {
  const list = useList<Row>("/staff/listings");
  const [error, setError] = useState<string | null>(null);

  async function decide(r: Row, decision: "approve" | "reject") {
    let note = "";
    if (decision === "reject") {
      note = window.prompt("Reason for rejecting this listing?") ?? "";
      if (!note.trim()) return;
    }
    try {
      await apiSend("POST", `/staff/listings/${r.kind}/${r.id}/${decision}`, { note });
      setError(null);
      list.reload();
      onChanged();
    } catch (e) {
      setError(errText(e));
    }
  }

  return (
    <div className="space-y-3">
      {error && <Alert tone="danger">{error}</Alert>}
      <p className="text-sm text-muted">
        Check that the link goes to a real posting, that nobody asks applicants to pay, and that the
        details match. Listings sent back by user reports also appear here.
      </p>
      <ListShell list={list} empty="No listings waiting for moderation.">
        {(rows) => (
          <DataTable caption="Listings waiting for moderation">
            <thead>
              <tr>
                <th className={th}>Listing</th>
                <th className={th}>Details</th>
                <th className={th}>By</th>
                <th className={th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.kind}-${r.id}`}>
                  <td className={td}>
                    <p className="font-medium">{r.title}</p>
                    <p className="text-xs text-muted">
                      {r.kind} · {r.organization} · {r.country_name ?? "no country"}
                    </p>
                    <a
                      className="text-primary underline"
                      href={r.apply_url}
                      rel="noopener noreferrer nofollow"
                      target="_blank"
                    >
                      Open posting
                    </a>
                  </td>
                  <td className={td}>
                    {r.description.slice(0, 200)}
                    {r.closes_on && <p className="text-xs text-muted">Closes {r.closes_on}</p>}
                  </td>
                  <td className={td}>
                    {r.submitted_by}
                    <p className="text-xs text-muted">{fmt(r.created_at)}</p>
                  </td>
                  <td className={`${td} space-x-2 whitespace-nowrap`}>
                    <Button onClick={() => decide(r, "approve")}>Approve</Button>
                    <Button variant="secondary" onClick={() => decide(r, "reject")}>
                      Reject
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </ListShell>
    </div>
  );
}
