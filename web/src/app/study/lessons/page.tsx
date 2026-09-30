import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { Breadcrumbs, EmptyState } from "@/components/ui/primitives";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Lessons",
  alternates: { canonical: "/study/lessons" },
};

interface LessonRow {
  slug: string;
  title: string;
  topic: string;
  subject: string;
}

export default async function LessonsPage() {
  const rows = await apiGet<LessonRow[]>("/study/lessons/");
  const bySubject = new Map<string, LessonRow[]>();
  for (const r of rows) bySubject.set(r.subject, [...(bySubject.get(r.subject) ?? []), r]);
  return (
    <main className="space-y-4">
      <Breadcrumbs items={[{ label: "Study", href: "/study" }, { label: "Lessons" }]} />
      <h1 className="text-xl font-semibold">Lessons</h1>
      {rows.length === 0 ? (
        <EmptyState title="No reviewed lessons yet.">
          Lessons are published only after editors add sources and a reviewer approves them.
        </EmptyState>
      ) : (
        [...bySubject.entries()].map(([subject, items]) => (
          <section key={subject} aria-label={subject} className="space-y-1">
            <h2 className="font-semibold">{subject}</h2>
            <ul className="space-y-1 text-sm">
              {items.map((l) => (
                <li key={l.slug}>
                  <Link className="text-primary underline" href={`/study/lessons/${l.slug}`}>
                    {l.title}
                  </Link>{" "}
                  <span className="text-muted">({l.topic})</span>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </main>
  );
}
