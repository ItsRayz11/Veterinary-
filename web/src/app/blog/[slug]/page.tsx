import type { Metadata } from "next";
import Link from "next/link";
import { ArticleBody } from "@/components/article-body";
import { JsonLd } from "@/components/json-ld";
import { Alert, Breadcrumbs } from "@/components/ui/primitives";
import { apiGet } from "@/lib/api";
import type { ArticleDetail } from "@/lib/content";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/blog/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const a = await apiGet<ArticleDetail>(`/articles/${slug}/`);
  return {
    title: a.meta_title,
    description: a.meta_description || undefined,
    alternates: { canonical: a.canonical_url || `/blog/${a.slug}` },
  };
}

export default async function ArticlePage({ params }: PageProps<"/blog/[slug]">) {
  const { slug } = await params;
  const a = await apiGet<ArticleDetail>(`/articles/${slug}/`);
  return (
    <article className="mx-auto max-w-2xl space-y-4">
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Article",
          headline: a.title,
          author: { "@type": "Person", name: a.author },
          datePublished: a.published_at,
          dateModified: a.updated_at,
          mainEntityOfPage: `${SITE_URL}/blog/${a.slug}`,
        }}
      />
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Articles", href: "/blog" },
          { label: a.title },
        ]}
      />
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{a.title}</h1>
        <p className="text-sm text-muted">
          {a.author}
          {a.published_at && ` · ${new Date(a.published_at).toLocaleDateString()}`}
          {a.category && ` · ${a.category}`}
        </p>
      </header>
      {a.medical && (
        <Alert tone="warn" title="Clinical content">
          Reviewed by a veterinarian reviewer. It does not replace clinical judgement or the product
          label.
        </Alert>
      )}
      {a.ai_assisted && (
        <p className="text-xs text-muted">Drafted with AI assistance and approved by an editor.</p>
      )}
      <ArticleBody text={a.body} />
      {a.references.length > 0 && (
        <section aria-labelledby="refs">
          <h2 id="refs" className="font-semibold">
            References
          </h2>
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {a.references.map((r) => (
              <li key={r}>
                <a
                  href={r}
                  rel="noopener noreferrer nofollow"
                  target="_blank"
                  className="break-all text-primary underline"
                >
                  {r}
                </a>
              </li>
            ))}
          </ol>
        </section>
      )}
      {a.related.length > 0 && (
        <section aria-labelledby="related">
          <h2 id="related" className="font-semibold">
            Related articles
          </h2>
          <ul className="list-disc pl-5 text-sm">
            {a.related.map((r) => (
              <li key={r.slug}>
                <Link href={`/blog/${r.slug}`} className="text-primary underline">
                  {r.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
