"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Field, Select, Skeleton, TextInput } from "@/components/ui/forms";
import { Modal } from "@/components/ui/modal";
import { Alert, DataTable, EmptyState, td, th } from "@/components/ui/primitives";
import { ClientApiError, apiFetch, apiSend } from "@/lib/client-api";

const STATUSES = [
  ["needs_verification", "Needs verification"],
  ["source_found_pending_review", "Source found, pending review"],
  ["manufacturer_supplied", "Manufacturer supplied"],
  ["official_regulatory", "Official regulatory source"],
  ["expert_reviewed", "Expert reviewed"],
  ["verified", "Verified"],
  ["deprecated", "Deprecated"],
  ["archived", "Archived"],
] as const;

const fmt = (iso: string) => new Date(iso).toLocaleString();
const errText = (e: unknown) => (e instanceof ClientApiError ? e.message : "Something went wrong.");

/** Loads a list endpoint; `reload` re-runs it. */
function useList<T>(path: string) {
  const [rows, setRows] = useState<T[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    apiFetch<{ results: T[] }>(path)
      .then((d) => live && (setRows(d?.results ?? []), setError(d ? null : "Not permitted.")))
      .catch(() => live && setError("Could not load this list."));
    return () => {
      live = false;
    };
  }, [path, n]);
  const reload = useCallback(() => setN((v) => v + 1), []);
  return { rows, error, reload };
}

function ListShell<T>({
  list,
  empty,
  children,
}: {
  list: { rows: T[] | null; error: string | null };
  empty: string;
  children: (rows: T[]) => React.ReactNode;
}) {
  if (list.error) return <Alert tone="danger">{list.error}</Alert>;
  if (!list.rows) return <Skeleton className="h-24 w-full" />;
  if (!list.rows.length) return <EmptyState title={empty} />;
  return <>{children(list.rows)}</>;
}

/* ---------- Review queue ---------- */

interface QueueItem {
  model: string;
  id: number;
  label: string;
  review_status: string;
  is_development_data: boolean;
  has_source: boolean;
  updated_at: string;
}
interface Version {
  date: string;
  by: string | null;
  created?: boolean;
  changes: { field: string; old: string; new: string }[];
}

export function ReviewQueueTab({
  counts,
  onChanged,
}: {
  counts: Record<string, number>;
  onChanged: () => void;
}) {
  const [model, setModel] = useState("");
  const list = useList<QueueItem>(`/staff/review-queue${model ? `?model=${model}` : ""}`);
  const [target, setTarget] = useState<QueueItem | null>(null);
  const [history, setHistory] = useState<{ label: string; versions: Version[] } | null>(null);
  const [status, setStatus] = useState<string>(STATUSES[1][0]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!target) return;
    setBusy(true);
    setError(null);
    try {
      await apiSend("POST", `/staff/review-queue/${target.model}/${target.id}/status`, {
        status,
        reason,
      });
      setTarget(null);
      setReason("");
      list.reload();
      onChanged();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function showHistory(item: QueueItem) {
    try {
      const h = await apiFetch<{ label: string; versions: Version[] }>(
        `/staff/review-queue/${item.model}/${item.id}/history`,
      );
      setHistory(h ?? { label: item.label, versions: [] });
    } catch {
      setHistory({ label: item.label, versions: [] });
    }
  }

  return (
    <div className="space-y-3">
      <Field id="model-filter" label="Record type">
        <Select id="model-filter" value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="">All types</option>
          {Object.entries(counts).map(([k, n]) => (
            <option key={k} value={k}>
              {k} ({n})
            </option>
          ))}
        </Select>
      </Field>
      <ListShell list={list} empty="Nothing waiting for review.">
        {(rows) => (
          <DataTable caption="Records waiting for review">
            <thead>
              <tr>
                <th className={th}>Record</th>
                <th className={th}>Type</th>
                <th className={th}>Status</th>
                <th className={th}>Source</th>
                <th className={th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.model}-${r.id}`}>
                  <td className={td}>
                    {r.label}
                    {r.is_development_data && (
                      <span className="ml-2 rounded bg-warn-bg px-1 text-xs text-warn">
                        development data
                      </span>
                    )}
                  </td>
                  <td className={td}>{r.model}</td>
                  <td className={td}>{r.review_status.replaceAll("_", " ")}</td>
                  <td className={td}>{r.has_source ? "Linked" : "None"}</td>
                  <td className={`${td} space-x-3 whitespace-nowrap`}>
                    <button className="text-primary underline" onClick={() => setTarget(r)}>
                      Change status
                    </button>
                    <button className="text-primary underline" onClick={() => showHistory(r)}>
                      History
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </ListShell>

      <Modal
        open={!!target}
        title={`Change status: ${target?.label ?? ""}`}
        onClose={() => setTarget(null)}
      >
        <div className="space-y-3">
          {error && <Alert tone="danger">{error}</Alert>}
          <Field
            id="new-status"
            label="New status"
            hint="Public statuses need a linked source; sign-off needs a veterinarian reviewer."
          >
            <Select id="new-status" value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUSES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="reason" label="Reason (recorded in the audit log)">
            <TextInput
              id="reason"
              value={reason}
              maxLength={300}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setTarget(null)}>
              Cancel
            </Button>
            <Button loading={busy} onClick={submit}>
              Apply
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={!!history}
        title={`History: ${history?.label ?? ""}`}
        onClose={() => setHistory(null)}
      >
        <div className="max-h-[60vh] space-y-3 overflow-y-auto text-sm">
          {history?.versions.length === 0 && <p className="text-muted">No history recorded.</p>}
          {history?.versions.map((v, i) => (
            <div key={i} className="rounded border border-border p-2">
              <p className="text-xs text-muted">
                {fmt(v.date)} by {v.by ?? "system"}
                {v.created ? " (created)" : ""}
              </p>
              <ul>
                {v.changes.map((c) => (
                  <li key={c.field}>
                    <span className="font-medium">{c.field}</span>:{" "}
                    <del className="text-danger">{c.old || "(empty)"}</del>{" "}
                    <ins className="text-ok no-underline">{c.new || "(empty)"}</ins>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-3 flex justify-end">
          <Button variant="secondary" onClick={() => setHistory(null)}>
            Close
          </Button>
        </div>
      </Modal>
    </div>
  );
}

/* ---------- Price submissions ---------- */

interface Submission {
  id: number;
  kind: string;
  product: string;
  country: string;
  region: string;
  city: string;
  currency: string;
  price_type: string;
  amount: string | null;
  target: string | null;
  note: string;
  evidence_url: string;
  submitted_by: string;
  created_at: string;
}

export function PricesTab({ onChanged }: { onChanged: () => void }) {
  const list = useList<Submission>("/staff/price-submissions");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [rejecting, setRejecting] = useState<Submission | null>(null);
  const [note, setNote] = useState("");

  async function decide(s: Submission, decision: "approve" | "reject", text: string) {
    setBusy(s.id);
    setError(null);
    try {
      await apiSend("POST", `/staff/price-submissions/${s.id}/${decision}`, { note: text });
      setRejecting(null);
      setNote("");
      list.reload();
      onChanged();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      {error && <Alert tone="danger">{error}</Alert>}
      <ListShell list={list} empty="No pending price submissions.">
        {(rows) => (
          <DataTable caption="Pending price submissions">
            <thead>
              <tr>
                <th className={th}>Product</th>
                <th className={th}>Submission</th>
                <th className={th}>Where</th>
                <th className={th}>By</th>
                <th className={th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id}>
                  <td className={td}>{s.product}</td>
                  <td className={td}>
                    {s.kind === "new_price"
                      ? `${s.currency} ${s.amount} (${s.price_type})`
                      : `Reports as incorrect: ${s.target}`}
                    {s.note && <p className="text-muted">{s.note}</p>}
                    {s.evidence_url && (
                      <a
                        className="text-primary underline"
                        href={s.evidence_url}
                        rel="noopener noreferrer nofollow"
                        target="_blank"
                      >
                        Evidence
                      </a>
                    )}
                  </td>
                  <td className={td}>{[s.city, s.region, s.country].filter(Boolean).join(", ")}</td>
                  <td className={td}>
                    {s.submitted_by}
                    <p className="text-xs text-muted">{fmt(s.created_at)}</p>
                  </td>
                  <td className={`${td} space-x-2 whitespace-nowrap`}>
                    <Button loading={busy === s.id} onClick={() => decide(s, "approve", "")}>
                      Approve
                    </Button>
                    <Button variant="secondary" onClick={() => setRejecting(s)}>
                      Reject
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </ListShell>
      <Modal open={!!rejecting} title="Reject submission" onClose={() => setRejecting(null)}>
        <div className="space-y-3">
          <Field id="reject-note" label="Reason (required)">
            <TextInput
              id="reject-note"
              value={note}
              maxLength={300}
              onChange={(e) => setNote(e.target.value)}
            />
          </Field>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setRejecting(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              disabled={!note.trim()}
              onClick={() => rejecting && decide(rejecting, "reject", note)}
            >
              Reject
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

/* ---------- Question reports ---------- */

interface Report {
  id: number;
  question_id: number;
  question: string;
  message: string;
  reporter: string;
  created_at: string;
}

export function QuestionReportsTab({ onChanged }: { onChanged: () => void }) {
  const list = useList<Report>("/staff/question-reports");
  const [error, setError] = useState<string | null>(null);

  async function resolve(r: Report) {
    try {
      await apiSend("POST", `/staff/question-reports/${r.id}/resolve`, {});
      list.reload();
      onChanged();
    } catch (e) {
      setError(errText(e));
    }
  }

  return (
    <div className="space-y-3">
      {error && <Alert tone="danger">{error}</Alert>}
      <ListShell list={list} empty="No open question reports.">
        {(rows) => (
          <ul className="space-y-2">
            {rows.map((r) => (
              <li key={r.id} className="rounded-md border border-border bg-surface p-3 text-sm">
                <p className="font-medium">{r.question}</p>
                <p className="mt-1">{r.message}</p>
                <p className="mt-1 text-xs text-muted">
                  {r.reporter}, {fmt(r.created_at)}
                </p>
                <Button variant="secondary" className="mt-2" onClick={() => resolve(r)}>
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

/* ---------- Audit log (admin) ---------- */

interface AuditRow {
  id: number;
  at: string;
  actor: string | null;
  action: string;
  object: string;
  reason: string;
}

export function AuditLogTab() {
  const list = useList<AuditRow>("/staff/audit-log");
  return (
    <ListShell list={list} empty="No audit entries yet.">
      {(rows) => (
        <DataTable caption="Most recent audit log entries">
          <thead>
            <tr>
              <th className={th}>When</th>
              <th className={th}>Who</th>
              <th className={th}>Action</th>
              <th className={th}>Object</th>
              <th className={th}>Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td className={td}>{fmt(a.at)}</td>
                <td className={td}>{a.actor ?? "system"}</td>
                <td className={td}>{a.action}</td>
                <td className={td}>{a.object}</td>
                <td className={td}>{a.reason}</td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      )}
    </ListShell>
  );
}
