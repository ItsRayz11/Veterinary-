import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { PastPaper } from "@/components/study/types";
import { Breadcrumbs, EmptyState } from "@/components/ui/primitives";
import { DocumentCard, MetadataBadge } from "@/components/ui/visual";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Past-paper index" };

export default async function PastPapersPage() {
  const papers = await apiGet<PastPaper[]>("/study/past-papers/");
  return (
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Study", href: "/study" }, { label: "Past papers" }]} />
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Past-paper index</h1>
      <p className="text-sm text-muted">
        Links to papers hosted by their legal owners. We do not copy or host exam papers.
      </p>
      {papers.length === 0 ? (
        <EmptyState title="No past papers indexed yet.">
          Entries are added only with a legal source link and licence note.
        </EmptyState>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {papers.map((p) => (
            <li key={p.url}>
              <DocumentCard
                href={p.url}
                title={p.course}
                source={p.university}
                note={p.license_note}
                badges={
                  <>
                    <MetadataBadge tone="blue">{p.exam_type}</MetadataBadge>
                    <MetadataBadge>{p.year}</MetadataBadge>
                  </>
                }
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
