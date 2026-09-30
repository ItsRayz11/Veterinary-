import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import type { PastPaper } from "@/components/study/types";
import { Breadcrumbs, DataTable, EmptyState, td, th } from "@/components/ui/primitives";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Past-paper index" };

export default async function PastPapersPage() {
  const papers = await apiGet<PastPaper[]>("/study/past-papers/");
  return (
    <main className="space-y-4">
      <Breadcrumbs items={[{ label: "Study", href: "/study" }, { label: "Past papers" }]} />
      <h1 className="text-xl font-semibold">Past-paper index</h1>
      <p className="text-sm text-muted">
        Links to papers hosted by their legal owners. We do not copy or host exam papers.
      </p>
      {papers.length === 0 ? (
        <EmptyState title="No past papers indexed yet.">
          Entries are added only with a legal source link and licence note.
        </EmptyState>
      ) : (
        <DataTable caption="Indexed past papers">
          <thead>
            <tr>
              <th className={th}>University</th>
              <th className={th}>Course</th>
              <th className={th}>Year</th>
              <th className={th}>Licence</th>
            </tr>
          </thead>
          <tbody>
            {papers.map((p) => (
              <tr key={p.url}>
                <td className={td}>{p.university}</td>
                <td className={td}>
                  <a
                    className="text-primary underline"
                    href={p.url}
                    rel="noopener noreferrer nofollow"
                    target="_blank"
                  >
                    {p.course}
                  </a>{" "}
                  ({p.exam_type})
                </td>
                <td className={td}>{p.year}</td>
                <td className={td}>{p.license_note}</td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      )}
    </main>
  );
}
