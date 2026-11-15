"use client";

import { RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Button, Field, Skeleton, TextInput } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { apiFetch, apiSend } from "@/lib/client-api";
import {
  Badge,
  IMAGE_TONE,
  ImageThumb,
  ProgressBar,
  RECOMMENDATION_TONE,
  SafeLink,
  SOURCE_TONE,
  type Tone,
} from "./pipeline-ui";
import { errText, fmt } from "./tabs";

export interface WorkspaceDetail {
  model: string;
  id: number;
  label: string;
  type: string;
  country: string;
  description: string;
  website: string;
  raw_source_url: string;
  review_status: string;
  is_development_data: boolean;
  has_source: boolean;
  sections: { title: string; items: { label: string; value: string; is_url: boolean }[] }[];
  sources: {
    id: number;
    title: string;
    publisher: string;
    url: string;
    license_note: string;
    license_url: string;
    provider: string;
    verification_status: string;
    verification_note: string;
    health: { ok: boolean; status_code: number | null; checked_at: string; error: string } | null;
  }[];
  images: {
    id: number;
    original_url: string;
    display_url: string;
    page_url: string;
    credit: string;
    license: string;
    license_url: string;
    status: string;
    status_detail: string;
    attempts: number;
    mime_type: string;
    size_bytes: number | null;
    in_r2: boolean;
  }[];
  r2_configured: boolean;
  assessment: {
    completeness: number;
    missing_fields: string[];
    issues: { code: string; label: string }[];
    duplicates: { model: string; id: number; label: string; reason: string }[];
    recommendation: string;
    recommendation_label: string;
    reasons: string[];
    trust: string;
    risk: string;
    source_state: string;
    provider: string;
    changed_fields: string[];
    changed_at: string | null;
  };
  timeline: {
    imported_at: string;
    last_synced_at: string;
    reviewed_at: string | null;
    reviewed_by: string | null;
  };
  audit: { at: string; actor: string | null; action: string; reason: string }[];
}

const VERIFY_TONE: Record<string, Tone> = {
  provenance_ok: "ok",
  unverified: "warn",
  conflict: "danger",
  invalid: "danger",
};

const ACTIONS = [
  { key: "approve", label: "Approve", status: "verified", needsReason: false, variant: "primary" },
  {
    key: "correct",
    label: "Request correction",
    status: "needs_verification",
    needsReason: true,
    variant: "secondary",
  },
  { key: "reject", label: "Reject", status: "archived", needsReason: true, variant: "danger" },
] as const;

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-border p-3">
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

/** Full review workspace: data, sources, images, assessment, history and decision actions.
 * Two columns on wide screens, one stacked column on phones; long URLs are shortened links. */
export function ReviewWorkspace({
  target,
  canApprove,
  onClose,
  onChanged,
}: {
  target: { model: string; id: number } | null;
  canApprove: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [d, setD] = useState<WorkspaceDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!target) return;
    try {
      setD(await apiFetch<WorkspaceDetail>(`/staff/review-queue/${target.model}/${target.id}`));
    } catch {
      setError("Could not load this record.");
    }
  }, [target]);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (target && !dlg.open) {
      setD(null);
      setError(null);
      setDone(null);
      setReason("");
      dlg.showModal();
      void load();
    }
    if (!target && dlg.open) dlg.close();
  }, [target, load]);

  async function decide(a: (typeof ACTIONS)[number]) {
    if (!d) return;
    if (a.needsReason && !reason.trim()) {
      setError("Give a reason; it is recorded in the audit log.");
      return;
    }
    setBusy(a.key);
    setError(null);
    try {
      await apiSend("POST", `/staff/review-queue/${d.model}/${d.id}/status`, {
        status: a.status,
        reason: reason || `${a.label} from the review workspace`,
      });
      setDone(`${a.label}: done.`);
      setReason("");
      onChanged();
      await load();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  async function repair() {
    if (!d) return;
    setBusy("repair");
    setError(null);
    try {
      await apiSend("POST", `/staff/records/${d.model}/${d.id}/repair`);
      setDone("Sources and images re-processed.");
      onChanged();
      await load();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  async function retryImage(id: number) {
    setBusy(`img${id}`);
    try {
      await apiSend("POST", `/staff/images/${id}/retry`);
      await load();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  const a = d?.assessment;
  const [srcTone, srcLabel] = SOURCE_TONE[a?.source_state ?? "none"] ?? ["muted", ""];

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby={titleId}
      className="m-auto h-[min(92vh,60rem)] w-[min(72rem,96vw)] overflow-hidden card p-0 text-text backdrop:bg-black/50"
    >
      <div className="flex h-full min-w-0 flex-col">
        <header className="flex items-start gap-2 border-b border-border p-3">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="break-words text-base font-semibold">
              {d?.label ?? "Loading…"}
            </h2>
            {d && (
              <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted">
                <span>{d.type}</span>
                {d.country && <span>· {d.country}</span>}
                <Badge tone="info">{d.review_status.replaceAll("_", " ")}</Badge>
                {d.is_development_data && <Badge tone="warn">development data</Badge>}
                <Badge tone={srcTone}>{srcLabel}</Badge>
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close review"
            className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-md hover:bg-black/5"
          >
            <X aria-hidden className="size-5" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-3 [overflow-wrap:anywhere]">
          {error && (
            <div className="mb-3">
              <Alert tone="danger">{error}</Alert>
            </div>
          )}
          {done && (
            <div className="mb-3">
              <Alert tone="ok">{done}</Alert>
            </div>
          )}
          {!d && !error && <Skeleton className="h-40 w-full" />}
          {d && a && (
            <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
              <div className="min-w-0 space-y-3">
                {d.description && (
                  <Card title="Description">
                    <p className="text-sm">{d.description}</p>
                  </Card>
                )}
                {d.sections
                  .filter((s) => s.title !== "Description")
                  .map((s) => (
                    <Card key={s.title} title={s.title}>
                      <dl className="grid grid-cols-1 gap-x-3 gap-y-1 text-sm sm:grid-cols-[9rem_minmax(0,1fr)]">
                        {s.items.map((i) => (
                          <div key={i.label} className="contents">
                            <dt className="text-muted">{i.label}</dt>
                            <dd className="min-w-0">
                              {i.is_url ? <SafeLink href={i.value} /> : i.value || "(empty)"}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </Card>
                  ))}

                <Card title="Images and R2 storage">
                  {!d.images.length && <p className="text-sm text-muted">No image referenced.</p>}
                  <ul className="space-y-3">
                    {d.images.map((im) => {
                      const [tone, label] = IMAGE_TONE[im.status] ?? ["muted", im.status];
                      return (
                        <li key={im.id} className="flex min-w-0 flex-wrap gap-3 text-sm">
                          <ImageThumb src={im.display_url} alt={`Image for ${d.label}`} />
                          <div className="min-w-0 flex-1 space-y-1">
                            <p className="flex flex-wrap items-center gap-1.5">
                              <Badge tone={tone}>{im.in_r2 ? "Stored in R2" : label}</Badge>
                              {im.license && <Badge>{im.license}</Badge>}
                              {im.size_bytes != null && (
                                <span className="text-xs text-muted">
                                  {Math.round(im.size_bytes / 1024)} KB
                                </span>
                              )}
                            </p>
                            {im.status_detail && <p className="text-xs">{im.status_detail}</p>}
                            {im.credit && <p className="text-xs">Credit: {im.credit}</p>}
                            <p className="flex flex-wrap gap-x-3 text-xs">
                              <SafeLink href={im.original_url} label="Original file" />
                              {im.page_url && (
                                <SafeLink href={im.page_url} label="Attribution page" />
                              )}
                              {im.license_url && <SafeLink href={im.license_url} label="Licence" />}
                            </p>
                            {(im.status === "failed" || im.status === "pending") && (
                              <Button
                                variant="secondary"
                                className="!min-h-9 !px-3"
                                loading={busy === `img${im.id}`}
                                disabled={!d.r2_configured}
                                onClick={() => retryImage(im.id)}
                              >
                                {im.status === "failed" ? "Retry" : "Store now"}
                              </Button>
                            )}
                            {!d.r2_configured && im.status !== "stored" && (
                              <p className="text-xs text-muted">
                                R2 is not configured on the server, so nothing is copied yet.
                              </p>
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </Card>

                <Card title="History and audit">
                  <dl className="mb-2 grid grid-cols-[8rem_minmax(0,1fr)] gap-y-1 text-sm">
                    <dt className="text-muted">Imported</dt>
                    <dd>{fmt(d.timeline.imported_at)}</dd>
                    <dt className="text-muted">Last synchronised</dt>
                    <dd>{fmt(d.timeline.last_synced_at)}</dd>
                    <dt className="text-muted">Reviewed</dt>
                    <dd>
                      {d.timeline.reviewed_at
                        ? `${fmt(d.timeline.reviewed_at)} by ${d.timeline.reviewed_by ?? "system"}`
                        : "Not yet"}
                    </dd>
                  </dl>
                  {a.changed_fields.length > 0 && (
                    <p className="mb-2 text-xs text-warn">
                      Changed since the previous import: {a.changed_fields.join(", ")}
                    </p>
                  )}
                  <ul className="space-y-1 text-xs">
                    {d.audit.map((e, i) => (
                      <li key={i} className="border-t border-border pt-1">
                        <span className="text-muted">{fmt(e.at)}</span> · {e.actor ?? "system"} ·{" "}
                        {e.action}
                        {e.reason && <span className="text-muted"> — {e.reason}</span>}
                      </li>
                    ))}
                    {!d.audit.length && <li className="text-muted">No audit events yet.</li>}
                  </ul>
                </Card>
              </div>

              <div className="min-w-0 space-y-3">
                <Card title="Pipeline recommendation">
                  <p className="mb-1">
                    <Badge tone={RECOMMENDATION_TONE[a.recommendation] ?? "muted"}>
                      {a.recommendation_label}
                    </Badge>
                  </p>
                  <ul className="list-disc pl-5 text-xs">
                    {a.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-muted">
                    Advice only. Publication still needs a person with the right role.
                  </p>
                </Card>

                <Card title="Sources">
                  {!d.sources.length && (
                    <div className="space-y-2 text-sm">
                      <Alert tone="danger">
                        No source is linked in the registry. A record cannot be made public without
                        one.
                      </Alert>
                      {d.raw_source_url && (
                        <p className="text-xs">
                          The record carries a plain URL, not yet a linked source:{" "}
                          <SafeLink href={d.raw_source_url} />
                        </p>
                      )}
                    </div>
                  )}
                  <ul className="space-y-2">
                    {d.sources.map((s) => (
                      <li key={s.id} className="min-w-0 rounded border border-border p-2 text-sm">
                        <p className="font-medium">{s.title}</p>
                        <p className="my-1 flex flex-wrap gap-1.5">
                          <Badge tone={VERIFY_TONE[s.verification_status] ?? "muted"}>
                            {s.verification_status === "provenance_ok"
                              ? "Provenance verified"
                              : s.verification_status}
                          </Badge>
                          {s.provider && <Badge>{s.provider}</Badge>}
                          {s.health && (
                            <Badge tone={s.health.ok ? "ok" : "danger"}>
                              {s.health.ok ? "Link works" : "Link failing"}
                            </Badge>
                          )}
                        </p>
                        <p className="text-xs">
                          <SafeLink href={s.url} />
                        </p>
                        {s.license_note && (
                          <p className="text-xs">
                            Licence: {s.license_note}{" "}
                            {s.license_url && <SafeLink href={s.license_url} label="terms" />}
                          </p>
                        )}
                        {s.verification_note && (
                          <p className="text-xs text-muted">{s.verification_note}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </Card>

                <Card title="Completeness and checks">
                  <ProgressBar value={a.completeness} max={100} label="Completeness" />
                  <p className="mt-1 text-xs">{a.completeness}% of expected fields present</p>
                  {a.missing_fields.length > 0 && (
                    <p className="mt-1 text-xs text-warn">Missing: {a.missing_fields.join(", ")}</p>
                  )}
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {a.issues.map((i) => (
                      <li key={i.code}>
                        <Badge tone="warn">{i.label}</Badge>
                      </li>
                    ))}
                    {!a.issues.length && (
                      <li>
                        <Badge tone="ok">No issues found</Badge>
                      </li>
                    )}
                  </ul>
                </Card>

                <Card title="Duplicate check">
                  {!a.duplicates.length && (
                    <p className="text-sm text-muted">No duplicate candidates found.</p>
                  )}
                  <ul className="space-y-1 text-sm">
                    {a.duplicates.map((x) => (
                      <li key={x.id}>
                        {x.label}{" "}
                        <span className="text-xs text-muted">
                          #{x.id} · {x.reason}
                        </span>
                      </li>
                    ))}
                  </ul>
                </Card>
              </div>
            </div>
          )}
        </div>

        {d && (
          <footer className="space-y-2 border-t border-border p-3">
            <Field
              id="ws-reason"
              label="Reason (recorded in the audit log)"
              hint={
                canApprove
                  ? "Required to reject or request a correction."
                  : "Approving needs a veterinarian reviewer or admin; you can still reject or request a correction."
              }
            >
              <TextInput
                id="ws-reason"
                value={reason}
                maxLength={300}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              {ACTIONS.map((x) => (
                <Button
                  key={x.key}
                  variant={x.variant}
                  loading={busy === x.key}
                  disabled={(x.key === "approve" && !canApprove) || !!busy}
                  onClick={() => decide(x)}
                >
                  {x.label}
                </Button>
              ))}
              <Button
                variant="secondary"
                className="sm:ml-auto"
                loading={busy === "repair"}
                disabled={!!busy}
                onClick={repair}
              >
                <RefreshCw aria-hidden className="mr-1 size-4" />
                Re-link sources and images
              </Button>
            </div>
          </footer>
        )}
      </div>
    </dialog>
  );
}
