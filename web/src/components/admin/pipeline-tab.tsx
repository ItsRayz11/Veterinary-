"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Field, Select, Skeleton, TextInput } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { apiFetch, apiSend } from "@/lib/client-api";
import { BulkDialog, type BulkSelection } from "./bulk-dialog";
import { Badge, IMAGE_TONE, RECOMMENDATION_TONE, SOURCE_TONE, type Tone } from "./pipeline-ui";
import { ReviewWorkspace } from "./review-workspace";
import { errText, fmt } from "./tabs";

interface Overview {
  total_imported: number;
  awaiting_review: number;
  assessed_in_queue: number;
  not_yet_processed: number;
  auto_processed: number;
  source_problems: number;
  duplicates: number;
  safe_eligible: number;
  images: { stored: number; pending: number; failed: number; rejected: number };
  r2: { configured: boolean; public_url: boolean };
  failed_imports: {
    runs_7d: number;
    held_sources: number;
    recent: { task: string; error: string; at: string }[];
  };
  last_successful_sync: string | null;
  last_runs: Record<string, string | null>;
}
interface Group {
  key: string;
  label: string;
  count: number;
}
interface Item {
  model: string;
  id: number;
  label: string;
  type: string;
  country: string;
  provider: string;
  review_status: string;
  is_development_data: boolean;
  source_state: string;
  completeness: number;
  issues: { code: string; label: string }[];
  recommendation: string;
  recommendation_label: string;
  image_state: string;
  duplicates: number;
}
interface Facets {
  type: Group[];
  country: Group[];
  provider: Group[];
  recommendation: Group[];
}

const GROUP_BY = [
  ["recommendation", "Recommended action"],
  ["issue", "Issue"],
  ["type", "Record type"],
  ["country", "Country"],
  ["provider", "Source provider"],
  ["batch", "Import batch (date)"],
  ["status", "Review status"],
  ["source", "Source state"],
  ["image", "Image status"],
  ["trust", "Trust level"],
  ["completeness", "Completeness"],
] as const;
const PARAM_OF: Record<string, string> = {
  type: "model",
  completeness: "band",
};
const param = (by: string) => PARAM_OF[by] ?? by;

function Stat({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: number | string;
  tone?: Tone;
  hint?: string;
}) {
  const color =
    tone === "danger"
      ? "text-danger"
      : tone === "warn"
        ? "text-warn"
        : tone === "ok"
          ? "text-ok"
          : "";
  return (
    <div className="card min-w-0 p-3">
      <span className="block text-xs text-muted">{label}</span>
      <span className={`mt-1 block text-2xl font-semibold ${color}`}>{value}</span>
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </div>
  );
}

function Dashboard({ isAdmin, reloadKey }: { isAdmin: boolean; reloadKey: number }) {
  const [o, setO] = useState<Overview | null>(null);
  const [n, setN] = useState(0);
  const [running, setRunning] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    apiFetch<Overview>("/staff/pipeline/overview").then((d) => live && setO(d));
    return () => {
      live = false;
    };
  }, [n, reloadKey]);

  async function run(task: string) {
    setRunning(task);
    setMsg(null);
    try {
      const r = await apiSend<{ status: string; error: string }>(
        "POST",
        `/staff/automation/run/${task}`,
      );
      setMsg(r.status === "ok" ? `${task}: finished.` : `${task}: ${r.error || r.status}`);
      setN((v) => v + 1);
    } catch (e) {
      setMsg(errText(e));
    } finally {
      setRunning(null);
    }
  }

  if (!o) return <Skeleton className="h-28 w-full" />;
  return (
    <section aria-label="Automation overview" className="space-y-2">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Imported records (unreviewed)" value={o.total_imported.toLocaleString()} />
        <Stat label="Awaiting human review" value={o.awaiting_review.toLocaleString()} />
        <Stat
          label="Processed automatically"
          value={o.auto_processed.toLocaleString()}
          tone="ok"
          hint={
            o.not_yet_processed
              ? `${o.not_yet_processed} not yet processed`
              : "queue fully processed"
          }
        />
        <Stat
          label="Eligible for safe batch approval"
          value={o.safe_eligible.toLocaleString()}
          tone="ok"
        />
        <Stat
          label="Missing or invalid source"
          value={o.source_problems.toLocaleString()}
          tone={o.source_problems ? "danger" : undefined}
        />
        <Stat
          label="Possible duplicates"
          value={o.duplicates.toLocaleString()}
          tone={o.duplicates ? "warn" : undefined}
        />
        <Stat
          label="Images in R2"
          value={o.images.stored.toLocaleString()}
          hint={`${o.images.pending} waiting · ${o.images.failed} failed · ${o.images.rejected} not permitted`}
          tone={o.images.failed ? "warn" : undefined}
        />
        <Stat
          label="Failed runs (7 days)"
          value={o.failed_imports.runs_7d}
          tone={o.failed_imports.runs_7d ? "danger" : undefined}
          hint={
            o.failed_imports.held_sources
              ? `${o.failed_imports.held_sources} source(s) held`
              : undefined
          }
        />
      </div>
      <p className="text-xs text-muted">
        Last successful sync: {o.last_successful_sync ? fmt(o.last_successful_sync) : "never"} ·
        Pipeline last ran:{" "}
        {o.last_runs["review-pipeline"] ? fmt(o.last_runs["review-pipeline"]) : "never"}
      </p>
      {!o.r2.configured && (
        <Alert tone="warn" title="Cloudflare R2 is not configured">
          Images stay as references. Set the R2_* server variables to start storing approved images.
        </Alert>
      )}
      {o.failed_imports.recent.map((r) => (
        <Alert key={r.at} tone="danger">
          {r.task} failed {fmt(r.at)}: {r.error}
        </Alert>
      ))}
      {isAdmin && (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            loading={running === "review-pipeline"}
            onClick={() => run("review-pipeline")}
          >
            Run pipeline now
          </Button>
          <Button
            variant="secondary"
            loading={running === "universities-sync"}
            onClick={() => run("universities-sync")}
          >
            Import next country now
          </Button>
          {msg && (
            <span className="text-sm" role="status">
              {msg}
            </span>
          )}
        </div>
      )}
    </section>
  );
}

function GroupItems({
  filters,
  onOpen,
  isSelected,
  toggle,
}: {
  filters: Record<string, string>;
  onOpen: (i: Item) => void;
  isSelected: (i: Item) => boolean;
  toggle: (i: Item) => void;
}) {
  const [rows, setRows] = useState<Item[]>([]);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const qs = new URLSearchParams({ ...filters, page: String(page) }).toString();
  useEffect(() => {
    let live = true;
    apiFetch<{ results: Item[]; count: number }>(`/staff/pipeline/items?${qs}`).then((d) => {
      if (!live || !d) return;
      setRows((prev) => (page === 1 ? d.results : [...prev, ...d.results]));
      setCount(d.count);
      setLoading(false);
    });
    return () => {
      live = false;
    };
    // `page` is part of qs
  }, [qs, page]);

  if (loading) return <Skeleton className="m-3 h-16 w-auto" />;
  return (
    <div>
      <ul className="divide-y divide-border">
        {rows.map((i) => {
          const [st, stLabel] = SOURCE_TONE[i.source_state] ?? ["muted", i.source_state];
          const [it, itLabel] = IMAGE_TONE[i.image_state] ?? ["muted", i.image_state];
          return (
            <li key={`${i.model}-${i.id}`} className="flex min-w-0 items-start gap-2 p-2">
              <input
                type="checkbox"
                className="mt-1 size-5 shrink-0"
                checked={isSelected(i)}
                onChange={() => toggle(i)}
                aria-label={`Select ${i.label}`}
              />
              <div className="min-w-0 flex-1 text-sm">
                <button
                  type="button"
                  onClick={() => onOpen(i)}
                  className="break-words text-left font-medium text-primary underline"
                >
                  {i.label}
                </button>
                <p className="text-xs text-muted">
                  {i.type}
                  {i.country && ` · ${i.country}`} · {i.provider} · {i.completeness}% complete
                </p>
                <p className="mt-1 flex flex-wrap gap-1">
                  <Badge tone={RECOMMENDATION_TONE[i.recommendation] ?? "muted"}>
                    {i.recommendation_label}
                  </Badge>
                  <Badge tone={st}>{stLabel}</Badge>
                  {i.image_state !== "none" && <Badge tone={it}>{itLabel}</Badge>}
                  {i.duplicates > 0 && (
                    <Badge tone="warn">{i.duplicates} duplicate candidate(s)</Badge>
                  )}
                  {i.is_development_data && <Badge tone="warn">development data</Badge>}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
      {rows.length < count && (
        <div className="p-2">
          <Button variant="secondary" onClick={() => setPage((p) => p + 1)}>
            Show more ({count - rows.length} left)
          </Button>
        </div>
      )}
    </div>
  );
}

export function PipelineTab({
  isAdmin,
  canApprove,
  onChanged,
}: {
  isAdmin: boolean;
  canApprove: boolean;
  onChanged: () => void;
}) {
  const [by, setBy] = useState<string>("recommendation");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [q, setQ] = useState("");
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [selected, setSelected] = useState<Map<string, [string, number]>>(new Map());
  const [filterSel, setFilterSel] = useState<Record<string, string> | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [opening, setOpening] = useState<{ model: string; id: number } | null>(null);

  const active = { ...filters, ...(q.trim() ? { q: q.trim() } : {}) };
  const activeKey = JSON.stringify(active);

  useEffect(() => {
    let live = true;
    apiFetch<Facets>("/staff/pipeline/facets").then((f) => live && setFacets(f));
    return () => {
      live = false;
    };
  }, [version]);

  useEffect(() => {
    let live = true;
    const qs = new URLSearchParams({ by, ...JSON.parse(activeKey) }).toString();
    apiFetch<{ groups: Group[] }>(`/staff/pipeline/groups?${qs}`)
      .then((d) => live && setGroups(d?.groups ?? []))
      .catch(() => live && setError("Could not load the groups."));
    return () => {
      live = false;
    };
  }, [by, activeKey, version]);

  const setFilter = (k: string, v: string) => {
    setFilters((f) => {
      const next = { ...f };
      if (v) next[k] = v;
      else delete next[k];
      return next;
    });
    setFilterSel(null);
    setSelected(new Map());
  };
  const keyOf = (i: Item) => `${i.model}:${i.id}`;
  const toggle = useCallback((i: Item) => {
    setFilterSel(null);
    setSelected((m) => {
      const next = new Map(m);
      const k = keyOf(i);
      if (next.has(k)) next.delete(k);
      else next.set(k, [i.model, i.id]);
      return next;
    });
  }, []);

  const selection: BulkSelection | null = filterSel
    ? { kind: "filter", filter: filterSel }
    : selected.size
      ? { kind: "ids", ids: [...selected.values()] }
      : null;
  const refresh = () => {
    setVersion((v) => v + 1);
    setSelected(new Map());
    setFilterSel(null);
    onChanged();
  };

  return (
    <div className="space-y-4">
      <Dashboard isAdmin={isAdmin} reloadKey={version} />

      <section aria-label="Find and filter" className="card space-y-3 p-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <Field id="pl-q" label="Search records" hint="Name, ID, source, country or category">
              <TextInput
                id="pl-q"
                type="search"
                value={q}
                maxLength={100}
                onChange={(e) => setQ(e.target.value)}
              />
            </Field>
          </div>
          <Field id="pl-scope" label="Show">
            <Select
              id="pl-scope"
              value={filters.scope ?? ""}
              onChange={(e) => setFilter("scope", e.target.value)}
            >
              <option value="">Waiting for review</option>
              <option value="all">All records</option>
            </Select>
          </Field>
          <Field id="pl-by" label="Group by">
            <Select id="pl-by" value={by} onChange={(e) => setBy(e.target.value)}>
              {GROUP_BY.map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          {(
            [
              ["model", "Record type", facets?.type],
              ["country", "Country", facets?.country],
              ["provider", "Source provider", facets?.provider],
              ["recommendation", "Recommended action", facets?.recommendation],
            ] as const
          ).map(([k, label, opts]) => (
            <Field key={k} id={`pl-${k}`} label={label}>
              <Select
                id={`pl-${k}`}
                value={filters[k] ?? ""}
                onChange={(e) => setFilter(k, e.target.value)}
              >
                <option value="">All</option>
                {opts?.map((g) => (
                  <option key={g.key} value={g.key}>
                    {g.label} ({g.count})
                  </option>
                ))}
              </Select>
            </Field>
          ))}
        </div>
        {Object.keys(filters).filter((k) => k !== "scope").length > 0 && (
          <Button
            variant="secondary"
            onClick={() => {
              setFilters(filters.scope ? { scope: filters.scope } : {});
              setSelected(new Map());
              setFilterSel(null);
            }}
          >
            Clear filters
          </Button>
        )}
      </section>

      {error && <Alert tone="danger">{error}</Alert>}

      {selection && (
        <div
          className="sticky top-2 z-10 card flex flex-wrap items-center gap-2 p-3"
          role="region"
          aria-label="Bulk actions"
        >
          <span className="text-sm font-medium">
            {selection.kind === "filter"
              ? "Everything in the chosen group is selected"
              : `${selection.ids.length} selected`}
          </span>
          <Button onClick={() => setBulkOpen(true)}>Bulk actions…</Button>
          <Button
            variant="secondary"
            onClick={() => {
              setSelected(new Map());
              setFilterSel(null);
            }}
          >
            Clear selection
          </Button>
        </div>
      )}

      <section aria-label="Grouped records" className="space-y-2">
        {!groups && <Skeleton className="h-24 w-full" />}
        {groups?.length === 0 && <Alert>No records match.</Alert>}
        {groups?.map((g) => {
          const gf: Record<string, string> = { ...active, [param(by)]: g.key };
          if (g.key === "" && by === "issue") delete gf.issue;
          return (
            <details key={g.key || "none"} className="card overflow-hidden">
              <summary className="flex min-h-11 cursor-pointer items-center gap-2 p-3 text-sm font-medium">
                <span className="min-w-0 flex-1 break-words">{g.label}</span>
                <span className="rounded-full bg-primary/15 px-2 text-xs">
                  {g.count.toLocaleString()}
                </span>
              </summary>
              <div className="border-t border-border">
                <div className="p-2">
                  <Button
                    variant="secondary"
                    className="!min-h-9"
                    onClick={() => {
                      setSelected(new Map());
                      setFilterSel(gf);
                    }}
                  >
                    Select whole group ({g.count})
                  </Button>
                </div>
                <GroupItems
                  filters={gf}
                  onOpen={(i) => setOpening({ model: i.model, id: i.id })}
                  isSelected={(i) => !!filterSel || selected.has(keyOf(i))}
                  toggle={toggle}
                />
              </div>
            </details>
          );
        })}
      </section>

      <BulkDialog
        open={bulkOpen}
        selection={selection}
        canApprove={canApprove}
        onClose={() => setBulkOpen(false)}
        onDone={refresh}
      />
      <ReviewWorkspace
        target={opening}
        canApprove={canApprove}
        onClose={() => setOpening(null)}
        onChanged={refresh}
      />
    </div>
  );
}
