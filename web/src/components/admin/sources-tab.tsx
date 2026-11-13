"use client";

import { CrudSection, type FieldDef } from "./crud-section";
import { fmt } from "./tabs";

interface SourceRow extends Record<string, unknown> {
  id: number;
  name: string;
  publisher: string;
  content_type: string;
  geography: string;
  method: string;
  priority: number;
  enabled: boolean;
  paused: boolean;
  reachable: boolean | null;
  update_available: boolean;
  terms_confirmed: boolean;
  import_enabled: boolean;
  can_import: boolean;
  last_checked_at: string | null;
  last_error: string;
  last_import_result: string;
  robots_status: string;
}

const FIELDS: FieldDef[] = [
  { name: "name", label: "Display name" },
  { name: "slug", label: "Slug", createOnly: true, hint: "Lowercase letters, numbers, hyphens" },
  { name: "publisher", label: "Owner / publisher" },
  { name: "country_iso2", label: "Country (ISO 2-letter)" },
  {
    name: "kind",
    label: "Source kind",
    type: "select",
    options: [
      ["regulator_list", "Regulator product list"],
      ["open_data", "Open data portal / API"],
      ["document", "Published document (PDF)"],
      ["portal", "Search portal"],
    ],
  },
  { name: "content_type", label: "Content type", hint: "e.g. product registrations, jobs" },
  { name: "geography", label: "Geography" },
  {
    name: "method",
    label: "Access method",
    type: "select",
    options: [
      ["api", "Official API"],
      ["feed", "RSS / structured feed"],
      ["file", "Published file download"],
      ["manual", "Manual upload / entry"],
      ["partner", "Supplier or partner feed"],
    ],
  },
  { name: "landing_url", label: "Public page URL", type: "url" },
  { name: "data_url", label: "Direct data / API URL", type: "url" },
  { name: "licence_note", label: "Terms / licence (as stated by the publisher)" },
  {
    name: "robots_status",
    label: "Robots / terms status",
    type: "select",
    options: [
      ["unknown", "Not yet checked"],
      ["allowed", "Automated access allowed"],
      ["restricted", "Automated access not allowed"],
      ["n/a", "Not applicable (API, partner, manual)"],
    ],
  },
  { name: "extraction_scope", label: "Allowed extraction scope", type: "textarea" },
  {
    name: "credentials_ref",
    label: "Credentials reference",
    hint: "Environment variable NAME on the server, never the key",
  },
  { name: "import_destination", label: "Import destination", hint: "e.g. pharma.product" },
  { name: "importer", label: "Importer key", hint: "Empty = monitor only" },
  { name: "priority", label: "Priority (1 = most trusted)", type: "number" },
  { name: "check_interval_hours", label: "Refresh every (hours)", type: "number" },
  { name: "rate_limit_per_hour", label: "Rate limit (requests/hour)", type: "number" },
  { name: "enabled", label: "Run scheduled reachability checks", type: "checkbox" },
  {
    name: "import_enabled",
    label: "Import enabled",
    type: "checkbox",
    hint: "needs importer and confirmed terms",
  },
  { name: "notes", label: "Internal notes", type: "textarea" },
];

function state(r: SourceRow): string {
  if (r.paused) return "Paused";
  if (r.last_checked_at === null) return "Not checked yet";
  if (r.reachable === false) return `Unreachable${r.last_error ? `: ${r.last_error}` : ""}`;
  if (r.reachable) return r.update_available ? "Reachable, update available" : "Reachable";
  return "Skipped";
}

export function SourcesTab() {
  return (
    <CrudSection<SourceRow>
      path="/staff/sources"
      caption="Source registry"
      empty="No sources registered yet."
      newLabel="Register a source"
      defaults={{
        method: "file",
        kind: "open_data",
        priority: 50,
        check_interval_hours: 24,
        rate_limit_per_hour: 60,
        enabled: true,
        robots_status: "unknown",
      }}
      intro="Where VetRef gets its data. Use official APIs, feeds, permitted files, partner feeds or manual uploads only. Nothing here is shown to the public, and imported records always start unreviewed."
      fields={FIELDS}
      columns={[
        {
          header: "Source",
          render: (r) => (
            <>
              <span className="font-medium">{r.name}</span>
              <p className="text-xs text-muted">
                {[r.publisher, r.content_type, r.geography].filter(Boolean).join(" · ")}
              </p>
            </>
          ),
        },
        { header: "Method", render: (r) => `${r.method} · priority ${r.priority}` },
        {
          header: "Status",
          render: (r) => (
            <>
              {state(r)}
              {r.last_checked_at && (
                <p className="text-xs text-muted">Checked {fmt(r.last_checked_at)}</p>
              )}
              {r.import_enabled && (
                <p className="text-xs text-muted">{r.last_import_result || "Import on"}</p>
              )}
            </>
          ),
        },
        {
          header: "Terms",
          render: (r) =>
            `${r.terms_confirmed ? "Confirmed" : "Not confirmed"} · robots ${r.robots_status}`,
        },
      ]}
      actions={[
        { label: "Run now", post: "check", show: (r) => !r.paused },
        { label: "Retry", post: "retry", show: (r) => !r.paused && r.reachable === false },
        { label: "Pause", post: "pause", show: (r) => !r.paused },
        { label: "Resume", post: "resume", show: (r) => r.paused },
        {
          label: "Confirm terms",
          post: "confirm-terms",
          show: (r) => !r.terms_confirmed,
          confirm: "Confirm you have read the publisher's terms and automated access is permitted?",
        },
        {
          label: "Import now",
          post: "import",
          show: (r) => r.can_import && r.import_enabled && r.terms_confirmed && !r.paused,
        },
      ]}
    />
  );
}
