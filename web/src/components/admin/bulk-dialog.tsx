"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Button, Field, Select, TextInput } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { apiSend } from "@/lib/client-api";
import { Badge, ProgressBar } from "./pipeline-ui";
import { errText } from "./tabs";

export type BulkSelection =
  { kind: "ids"; ids: [string, number][] } | { kind: "filter"; filter: Record<string, string> };

interface Preview {
  selected: number;
  eligible: number;
  skipped: number;
  skipped_reasons: Record<string, number>;
  sample: { model: string; id: number; label: string; eligible: boolean; detail: string }[];
  truncated: boolean;
  max_targets: number;
}
interface Op {
  id: number;
  status: "running" | "done" | "partial";
  total: number;
  processed: number;
  succeeded: number;
  skipped: number;
  failed: number;
  results?: { model: string; id: number; label: string; outcome: string; detail: string }[];
}

const ACTIONS = [
  ["link_sources", "Repair source links", "Link raw URLs to registry sources and validate them."],
  [
    "revalidate",
    "Re-validate metadata",
    "Re-check publisher identity and licence of linked sources.",
  ],
  ["process_images", "Process images", "Store permitted, licensed images in Cloudflare R2."],
  [
    "approve_safe",
    "Approve safe records",
    "Only records the policy marks eligible; needs a veterinarian reviewer or admin.",
  ],
] as const;

const body = (sel: BulkSelection) =>
  sel.kind === "ids" ? { ids: sel.ids } : { filter: sel.filter };

/** Preview -> confirm -> chunked execution with progress, results and retry of failures. */
export function BulkDialog({
  open,
  selection,
  canApprove,
  onClose,
  onDone,
}: {
  open: boolean;
  selection: BulkSelection | null;
  canApprove: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [action, setAction] = useState<string>(ACTIONS[0][0]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [reason, setReason] = useState("");
  const [op, setOp] = useState<Op | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      setPreview(null);
      setOp(null);
      setError(null);
      setReason("");
      d.showModal();
    }
    if (!open && d.open) d.close();
  }, [open]);

  async function doPreview() {
    if (!selection) return;
    setBusy(true);
    setError(null);
    try {
      setPreview(
        await apiSend<Preview>("POST", "/staff/pipeline/bulk/preview", {
          action,
          ...body(selection),
        }),
      );
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function drive(first: Op) {
    let cur = first;
    setOp(cur);
    while (cur.status === "running") {
      cur = await apiSend<Op>("POST", `/staff/pipeline/bulk/${cur.id}/step`);
      setOp(cur);
    }
    onDone();
  }

  async function confirm() {
    if (!selection || !preview) return;
    setBusy(true);
    setError(null);
    try {
      const started = await apiSend<Op>("POST", "/staff/pipeline/bulk/start", {
        action,
        ...body(selection),
        expected_count: preview.eligible,
        reason,
      });
      await drive(started);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function retry() {
    if (!op) return;
    setBusy(true);
    setError(null);
    try {
      await drive(await apiSend<Op>("POST", `/staff/pipeline/bulk/${op.id}/retry`));
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  const needsReason = action === "approve_safe";
  const running = op?.status === "running";
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby={titleId}
      className="m-auto max-h-[92vh] w-[min(40rem,96vw)] overflow-y-auto card p-4 text-text backdrop:bg-black/50"
    >
      <h2 id={titleId} className="mb-3 text-base font-semibold">
        Bulk actions
      </h2>
      <div className="space-y-3 text-sm [overflow-wrap:anywhere]">
        {error && <Alert tone="danger">{error}</Alert>}
        {!op && (
          <>
            <Field id="bulk-action" label="Action" hint={ACTIONS.find((a) => a[0] === action)?.[2]}>
              <Select
                id="bulk-action"
                value={action}
                onChange={(e) => {
                  setAction(e.target.value);
                  setPreview(null);
                }}
              >
                {ACTIONS.map(([k, l]) => (
                  <option key={k} value={k} disabled={k === "approve_safe" && !canApprove}>
                    {l}
                    {k === "approve_safe" && !canApprove ? " (needs a veterinarian reviewer)" : ""}
                  </option>
                ))}
              </Select>
            </Field>
            <Button variant="secondary" loading={busy && !preview} onClick={doPreview}>
              Preview changes
            </Button>
          </>
        )}

        {preview && !op && (
          <div className="space-y-2" aria-live="polite">
            <p>
              <strong>{preview.eligible}</strong> of {preview.selected} selected records will be
              changed; {preview.skipped} will be left alone. Nothing has been changed yet.
            </p>
            {preview.truncated && (
              <Alert tone="warn">
                Only the first {preview.max_targets} matching records are included. Run again for
                the rest.
              </Alert>
            )}
            {Object.entries(preview.skipped_reasons).length > 0 && (
              <details>
                <summary className="cursor-pointer">Why records are skipped</summary>
                <ul className="mt-1 list-disc pl-5 text-xs">
                  {Object.entries(preview.skipped_reasons).map(([r, n]) => (
                    <li key={r}>
                      {n} × {r}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <details>
              <summary className="cursor-pointer">Sample of planned changes</summary>
              <ul className="mt-1 space-y-1 text-xs">
                {preview.sample.slice(0, 15).map((s) => (
                  <li key={`${s.model}-${s.id}`}>
                    <Badge tone={s.eligible ? "ok" : "muted"}>
                      {s.eligible ? "will change" : "skipped"}
                    </Badge>{" "}
                    {s.label}: {s.detail}
                  </li>
                ))}
              </ul>
            </details>
            <Field
              id="bulk-reason"
              label={needsReason ? "Reason (required, audited)" : "Note (optional, audited)"}
            >
              <TextInput
                id="bulk-reason"
                value={reason}
                maxLength={300}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
            <Button
              loading={busy}
              disabled={preview.eligible === 0 || (needsReason && !reason.trim())}
              onClick={confirm}
            >
              Apply to {preview.eligible} record{preview.eligible === 1 ? "" : "s"}
            </Button>
          </div>
        )}

        {op && (
          <div className="space-y-2" aria-live="polite">
            <ProgressBar value={op.processed} max={op.total} label="Bulk progress" />
            <p>
              {op.processed} of {op.total} processed · {op.succeeded} done · {op.skipped} skipped ·{" "}
              {op.failed} failed
              {running && " …"}
            </p>
            {!running && op.failed > 0 && (
              <>
                <Alert tone="warn">Some records failed. Failed ones can be retried.</Alert>
                <ul className="space-y-1 text-xs">
                  {op.results
                    ?.filter((r) => r.outcome === "failed")
                    .slice(0, 10)
                    .map((r) => (
                      <li key={`${r.model}-${r.id}`}>
                        {r.label}: {r.detail}
                      </li>
                    ))}
                </ul>
                <Button variant="secondary" loading={busy} onClick={retry}>
                  Retry failed ({op.failed})
                </Button>
              </>
            )}
            {!running && op.failed === 0 && (
              <Alert tone="ok">Finished. Every change is in the audit log.</Alert>
            )}
          </div>
        )}
      </div>
      <div className="mt-4 flex justify-end">
        <Button variant="secondary" disabled={!!running} onClick={onClose}>
          Close
        </Button>
      </div>
    </dialog>
  );
}
