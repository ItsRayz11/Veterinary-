import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import type { ArticleSummary } from "@/lib/content";
import { Breadcrumbs, EmptyState } from "@/components/ui/primitives";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Articles",
  description: "Articles on veterinary medicines, study and practice from the VetRef community.",
  alternates: { canonical: "/blog" },
};

export default async function BlogIndex() {
  const { results } = await apiGet<{ results: ArticleSummary[] }>("/articles/", 60);
  return (
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Articles" }]} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Articles</h1>
        <Link href="/blog/submit" className="text-sm text-primary underline">
          Write an article
        </Link>
      </div>
      {results.length === 0 ? (
        <EmptyState title="No articles published yet.">
          <Link href="/blog/submit" className="underline">
            Submit the first one
          </Link>
          . Every article is reviewed by an editor before it appears.
        </EmptyState>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {results.map((a) => (
            <li key={a.slug} className="card p-4">
              <Link href={`/blog/${a.slug}`} className="font-semibold hover:underline">
                {a.title}
              </Link>
              {a.excerpt && <p className="mt-1 text-sm text-muted">{a.excerpt}</p>}
              <p className="mt-2 text-xs text-muted">
                {a.author}
                {a.published_at && ` · ${new Date(a.published_at).toLocaleDateString()}`}
                {a.category && ` · ${a.category}`}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
