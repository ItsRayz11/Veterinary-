"use client";

import { useState } from "react";
import { Button } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { apiSend } from "@/lib/client-api";
import { CrudSection, type FieldDef } from "./crud-section";
import { errText, fmt } from "./tabs";

interface ArticleRow extends Record<string, unknown> {
  id: number;
  title: string;
  slug: string;
  status: string;
  author: string;
  medical: boolean;
  ai_assisted: boolean;
  reviewed_by: string | null;
  publish_at: string | null;
  reject_reason: string;
  revision: number;
  links: string[];
}
interface TopicRow extends Record<string, unknown> {
  id: number;
  title: string;
  rationale: string;
  basis: string;
  basis_label: string;
  status: string;
}

const ARTICLE_FIELDS: FieldDef[] = [
  { name: "title", label: "Title" },
  { name: "excerpt", label: "Summary" },
  { name: "body", label: "Body", type: "textarea", hint: "# headings, - lists, [text](https://…)" },
  { name: "category", label: "Category" },
  { name: "tags", label: "Tags (comma separated)" },
  { name: "author_credit", label: "Author credit (optional)" },
  { name: "references", label: "References (https, one per line)", type: "textarea" },
  { name: "meta_title", label: "SEO title" },
  { name: "meta_description", label: "SEO description" },
  { name: "canonical_url", label: "Canonical URL (optional)", type: "url" },
  { name: "publish_at", label: "Publish at (ISO date, for scheduling)" },
  {
    name: "medical",
    label: "Clinical content",
    type: "checkbox",
    hint: "needs a veterinarian reviewer and references",
  },
];
const TOPIC_FIELDS: FieldDef[] = [
  { name: "title", label: "Title" },
  { name: "rationale", label: "Rationale" },
  { name: "evidence_url", label: "Evidence link", type: "url" },
  {
    name: "status",
    label: "Status",
    type: "select",
    options: [
      ["new", "New"],
      ["accepted", "Accepted"],
      ["dismissed", "Dismissed"],
    ],
  },
];

export function ContentTab() {
  const [note, setNote] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);

  async function suggest() {
    setBusy(true);
    try {
      const r = await apiSend<{ created: number; duplicates_skipped: number; note: string }>(
        "POST",
        "/staff/articles/suggest-topics/",
        {},
      );
      setNote(
        `${r.created} new idea(s), ${r.duplicates_skipped} duplicate(s) skipped. ${r.note}`.trim(),
      );
      setVersion((v) => v + 1);
    } catch (e) {
      setNote(errText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="space-y-2" aria-label="Articles">
        <h3 className="font-semibold">Articles</h3>
        <CrudSection<ArticleRow>
          path="/staff/articles"
          caption="Articles"
          empty="No articles yet. Write one or wait for contributor submissions."
          newLabel="Write an article"
          intro="You can always write, edit and publish manually. Contributor submissions arrive as In review. Clinical articles need a veterinarian reviewer or admin and cited references. Editing a published article sends it back for review."
          fields={ARTICLE_FIELDS}
          columns={[
            {
              header: "Article",
              render: (r) => (
                <>
                  <span className="font-medium">{r.title}</span>
                  <p className="text-xs text-muted">
                    {r.author} · r{r.revision}
                    {r.medical && " · clinical"}
                    {r.ai_assisted && " · AI-assisted"}
                  </p>
                </>
              ),
            },
            {
              header: "Status",
              render: (r) => (
                <>
                  {r.status}
                  {r.publish_at && <p className="text-xs text-muted">{fmt(r.publish_at)}</p>}
                  {r.reject_reason && <p className="text-xs text-danger">{r.reject_reason}</p>}
                </>
              ),
            },
          ]}
          actions={[
            { label: "Publish", post: "publish", show: (r) => r.status !== "published" },
            {
              label: "Schedule",
              post: "schedule",
              show: (r) => r.status !== "published" && r.status !== "scheduled",
            },
            { label: "Send to review", post: "submit", show: (r) => r.status === "draft" },
            {
              label: "Unpublish",
              post: "unpublish",
              show: (r) => r.status === "published" || r.status === "scheduled",
            },
            {
              label: "Reject",
              danger: true,
              show: (r) => r.status === "review",
              run: async (r) => {
                const reason = window.prompt("Reason for rejecting (shown to the editors):");
                if (reason) await apiSend("POST", `/staff/articles/${r.id}/reject/`, { reason });
              },
            },
            {
              label: "Check links",
              run: async (r) => {
                const out = await apiSend<{ results: { url: string; ok: boolean }[] }>(
                  "POST",
                  `/staff/articles/${r.id}/check-links/`,
                  {},
                );
                const bad = out.results.filter((x) => !x.ok);
                window.alert(
                  out.results.length === 0
                    ? "No outbound links."
                    : bad.length
                      ? `Broken or unreachable:\n${bad.map((b) => b.url).join("\n")}`
                      : `All ${out.results.length} links respond.`,
                );
              },
            },
          ]}
        />
      </section>

      <section className="space-y-2" aria-label="Topic ideas">
        <h3 className="font-semibold">Editorial assistant: topic ideas</h3>
        <p className="text-sm text-muted">
          Ideas are labelled by what they rest on. VetRef has no trend feed registered, so none are
          labelled as trend data. Accepting an idea with &ldquo;Draft with AI&rdquo; creates an
          unpublished, AI-assisted, clinical-flagged draft and needs a configured AI provider.
        </p>
        <Button variant="secondary" loading={busy} onClick={suggest}>
          Find new topic ideas
        </Button>
        {note && <Alert tone="info">{note}</Alert>}
        <CrudSection<TopicRow>
          key={version}
          path="/staff/topics"
          caption="Topic ideas"
          empty="No ideas yet."
          canCreate={false}
          fields={TOPIC_FIELDS}
          columns={[
            { header: "Idea", render: (r) => r.title },
            { header: "Based on", render: (r) => r.basis_label },
            { header: "Why", render: (r) => r.rationale },
            { header: "Status", render: (r) => r.status },
          ]}
          actions={[
            {
              label: "Draft with AI",
              show: (r) => r.status === "new",
              run: (r) => apiSend("POST", `/staff/topics/${r.id}/draft/`, {}),
            },
          ]}
        />
      </section>
    </div>
  );
}
