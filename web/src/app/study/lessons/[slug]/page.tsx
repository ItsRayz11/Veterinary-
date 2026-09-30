import type { Metadata } from "next";
import { apiGet, type SourceRef, type Status } from "@/lib/api";
import { SourcesList } from "@/components/sources-list";
import { StatusLine } from "@/components/status-line";
import { Breadcrumbs, Section } from "@/components/ui/primitives";

interface LessonDetail {
  slug: string;
  title: string;
  topic: string;
  subject: string;
  body: string;
  sources: SourceRef[];
  status: Status;
}

export async function generateMetadata({
  params,
}: PageProps<"/study/lessons/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const l = await apiGet<LessonDetail>(`/study/lessons/${slug}/`);
  return { title: l.title, alternates: { canonical: `/study/lessons/${l.slug}` } };
}

export default async function LessonPage({ params }: PageProps<"/study/lessons/[slug]">) {
  const { slug } = await params;
  const l = await apiGet<LessonDetail>(`/study/lessons/${slug}/`);
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Breadcrumbs
        items={[
          { label: "Study", href: "/study" },
          { label: "Lessons", href: "/study/lessons" },
          { label: l.title },
        ]}
      />
      <h1 className="text-2xl font-semibold">{l.title}</h1>
      <p className="text-sm text-muted">
        {l.subject} · {l.topic}
      </p>
      <StatusLine status={l.status} />
      <div className="space-y-3 text-sm leading-relaxed">
        {l.body
          .split(/\n\s*\n/)
          .filter(Boolean)
          .map((p, i) => (
            <p key={i}>{p}</p>
          ))}
      </div>
      <Section id="sources" title="Sources">
        <SourcesList sources={l.sources} />
      </Section>
    </div>
  );
}
