import type { Metadata } from "next";
import { apiGet } from "@/lib/api";
import { Breadcrumbs, EmptyState } from "@/components/ui/primitives";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Book references",
  alternates: { canonical: "/study/books" },
};

interface Book {
  title: string;
  authors: string;
  edition: string;
  isbn: string;
  subject: string | null;
  url: string;
  note: string;
}

export default async function BooksPage() {
  const books = await apiGet<Book[]>("/study/books/");
  return (
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Study", href: "/study" }, { label: "Books" }]} />
      <h1 className="text-xl font-semibold">Book references</h1>
      <p className="text-sm text-muted">Titles are cited only; we do not host book text.</p>
      {books.length === 0 ? (
        <EmptyState title="No book references yet." />
      ) : (
        <ul className="space-y-2">
          {books.map((b) => (
            <li key={b.title} className="rounded-md border border-border bg-surface p-3 text-sm">
              <p className="font-medium">
                {b.url ? (
                  <a
                    className="text-primary underline"
                    href={b.url}
                    rel="noopener noreferrer nofollow"
                    target="_blank"
                  >
                    {b.title}
                  </a>
                ) : (
                  b.title
                )}
              </p>
              <p className="text-muted">
                {[b.authors, b.edition && `${b.edition} ed.`, b.isbn && `ISBN ${b.isbn}`, b.subject]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              {b.note && <p>{b.note}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
