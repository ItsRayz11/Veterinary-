import { FileSearch } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { CategoryIcon, type CategoryName } from "@/components/ui/icons";
import { SITE_URL } from "@/lib/site";

/**
 * Google requires `item` (a URL) on every breadcrumb except the last. A middle crumb that has no
 * page of its own (for example a section with no index page) is left out of the structured data,
 * and the remaining crumbs are renumbered. The visible trail is unchanged.
 */
export function breadcrumbJsonLd(items: { label: string; href?: string }[]) {
  const usable = items.filter((it, i) => it.href || i === items.length - 1);
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: usable.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.label,
      ...(it.href ? { item: `${SITE_URL}${it.href}` } : {}),
    })),
  };
}

export function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  const jsonLd = breadcrumbJsonLd(items);
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-muted">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }}
      />
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((it, i) => (
          <li key={it.label} className="flex items-center gap-1">
            {i > 0 && <span aria-hidden="true">/</span>}
            {it.href ? (
              <Link href={it.href} className="hover:underline">
                {it.label}
              </Link>
            ) : (
              <span aria-current="page" className="text-text">
                {it.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

const ALERT = {
  info: "bg-info-bg text-info",
  warn: "bg-warn-bg text-warn",
  danger: "bg-danger-bg text-danger",
  ok: "bg-ok-bg text-ok",
} as const;

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: keyof typeof ALERT;
  title?: string;
  children: ReactNode;
}) {
  return (
    <div
      role={tone === "danger" ? "alert" : "note"}
      className={`rounded-[var(--radius-md)] px-4 py-3 text-sm ${ALERT[tone]}`}
    >
      {title && <p className="font-medium">{title}</p>}
      <div>{children}</div>
    </div>
  );
}

export function Section({
  id,
  title,
  category,
  children,
}: {
  id: string;
  title: string;
  category?: CategoryName;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-28">
      <h2 id={`${id}-h`} className="mb-4 flex items-center gap-2 text-lg font-medium">
        {category && <CategoryIcon category={category} size={18} className="text-muted" />}
        {title}
      </h2>
      {children}
    </section>
  );
}

/** Horizontally scrollable table wrapper with a required caption for screen readers. */
export function DataTable({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className="card max-h-[70vh] overflow-auto">
      <table className="data-table w-full min-w-[32rem] border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

export const th =
  "sticky top-0 z-[1] border-b border-border bg-surface-2 px-3 py-2.5 font-medium text-muted";
export const td = "border-b border-border px-3 py-2 align-top";

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-[var(--radius-lg)] border border-dashed border-border bg-surface p-5 text-sm">
      <FileSearch
        size={22}
        strokeWidth={1.5}
        aria-hidden="true"
        className="mt-0.5 shrink-0 text-muted"
      />
      <div>
        <p className="font-medium">{title}</p>
        {children && <p className="mt-1 text-muted">{children}</p>}
      </div>
    </div>
  );
}

export function SectionNav({ items }: { items: { id: string; label: string }[] }) {
  return (
    <nav
      aria-label="On this page"
      className="chrome-bar sticky top-16 z-10 -mx-4 overflow-x-auto border-b px-4 sm:-mx-6 sm:px-6"
    >
      <ul className="flex gap-5 whitespace-nowrap text-sm">
        {items.map((i) => (
          <li key={i.id}>
            <a
              href={`#${i.id}`}
              className="inline-flex min-h-11 items-center text-text-2 hover:text-primary"
            >
              {i.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Consistent page title block: breadcrumbs sit above it, an optional lead below. */
export function PageHeader({
  title,
  lead,
  children,
}: {
  title: string;
  lead?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="space-y-3">
      <h1 className="text-[32px] sm:text-[40px]">{title}</h1>
      {lead && <div className="max-w-2xl text-[15px] leading-relaxed text-text-2">{lead}</div>}
      {children}
    </header>
  );
}

/** A tile for bento grids and link lists. Pass `href` to make the whole tile a link. */
export function Tile({ href, title, desc }: { href: string; title: string; desc?: string }) {
  return (
    <Link href={href} className="card card-link block p-5">
      <span className="font-medium">{title}</span>
      {desc && <span className="mt-1 block text-sm text-muted">{desc}</span>}
    </Link>
  );
}
