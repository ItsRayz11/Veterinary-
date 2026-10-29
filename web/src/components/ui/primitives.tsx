import Link from "next/link";
import type { ReactNode } from "react";

export function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-muted">
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
      className={`rounded-md p-3 text-sm ${ALERT[tone]}`}
    >
      {title && <p className="font-semibold">{title}</p>}
      <div>{children}</div>
    </div>
  );
}

export function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="scroll-mt-28">
      <h2 id={`${id}-h`} className="mb-3 text-lg font-semibold tracking-tight">
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
    <div className="rounded-lg border border-dashed border-border bg-surface/60 p-5 text-sm">
      <p className="font-medium">{title}</p>
      {children && <p className="mt-1 text-muted">{children}</p>}
    </div>
  );
}

export function SectionNav({ items }: { items: { id: string; label: string }[] }) {
  return (
    <nav
      aria-label="On this page"
      className="glass sticky top-14 z-10 -mx-4 overflow-x-auto px-4 sm:rounded-lg"
    >
      <ul className="flex gap-4 whitespace-nowrap py-2 text-sm">
        {items.map((i) => (
          <li key={i.id}>
            <a href={`#${i.id}`} className="text-muted hover:text-text">
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
    <header className="space-y-2">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      {lead && <div className="max-w-2xl text-sm text-muted">{lead}</div>}
      {children}
    </header>
  );
}

/** A tile for bento grids and link lists. Pass `href` to make the whole tile a link. */
export function Tile({ href, title, desc }: { href: string; title: string; desc?: string }) {
  return (
    <Link href={href} className="card card-link block p-4">
      <span className="font-medium">{title}</span>
      {desc && <span className="mt-1 block text-sm text-muted">{desc}</span>}
    </Link>
  );
}
