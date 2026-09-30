import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { Breadcrumbs, EmptyState } from "@/components/ui/primitives";

interface ClassDetail {
  slug: string;
  name: string;
  ancestors: { slug: string; name: string }[];
  children: { slug: string; name: string }[];
  generics: { name: string; slug: string; drug_class: string | null }[];
}

export async function generateMetadata({
  params,
}: PageProps<"/classes/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const c = await apiGet<ClassDetail>(`/drug-classes/${slug}/`);
  return { title: c.name, alternates: { canonical: `/classes/${c.slug}` } };
}

export default async function ClassPage({ params }: PageProps<"/classes/[slug]">) {
  const { slug } = await params;
  const c = await apiGet<ClassDetail>(`/drug-classes/${slug}/`);
  return (
    <div className="space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Drug classes", href: "/classes" },
          ...c.ancestors.map((a) => ({ label: a.name, href: `/classes/${a.slug}` })),
          { label: c.name },
        ]}
      />
      <h1 className="text-2xl font-semibold">{c.name}</h1>
      {c.children.length > 0 && (
        <p className="flex flex-wrap gap-3 text-sm">
          {c.children.map((k) => (
            <Link key={k.slug} className="text-primary underline" href={`/classes/${k.slug}`}>
              {k.name}
            </Link>
          ))}
        </p>
      )}
      {c.generics.length === 0 ? (
        <EmptyState title="No reviewed drugs in this class yet." />
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {c.generics.map((g) => (
            <li key={g.slug}>
              <Link
                href={`/drugs/${g.slug}`}
                className="block rounded-md border border-border bg-surface p-3 hover:border-primary"
              >
                <span className="font-medium">{g.name}</span>
                {g.drug_class && <span className="block text-sm text-muted">{g.drug_class}</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
