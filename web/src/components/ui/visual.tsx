import Link from "next/link";
import { ArrowRight, FileText, Landmark, Coins, Pill } from "lucide-react";
import type { ReactNode } from "react";
import { CalcArt } from "./calc-art";
import { CountryMap } from "./country-map";
import { Flag, flagAccent } from "./flag";
import { CategoryIcon, IconChip, type CategoryName, type Tone } from "./icons";
import type { LucideIcon } from "lucide-react";

/** Page `h1` with a category icon chip, matching the detail-page headers. */
export function PageTitle({ category, children }: { category: CategoryName; children: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <IconChip category={category} size="lg" />
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{children}</h1>
    </div>
  );
}

/** Compact row of links to tools or indexes that apply to the page. Only generic, always-valid links. */
export function RelatedResources({
  items,
}: {
  items: { href: string; label: string; category: CategoryName }[];
}) {
  return (
    <nav aria-label="Related resources">
      <ul className="flex flex-wrap gap-2">
        {items.map((i) => (
          <li key={i.href}>
            <Link
              href={i.href}
              className="neo inline-flex min-h-9 items-center gap-1.5 rounded-full px-3 text-sm"
            >
              <CategoryIcon category={i.category} size={15} className="text-primary" />
              {i.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Section title with an optional category glyph and a trailing action link. */
export function SectionHeader({
  id,
  title,
  category,
  action,
}: {
  id: string;
  title: string;
  category?: CategoryName;
  action?: { href: string; label: string };
}) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 id={id} className="flex items-center gap-2 text-base font-semibold tracking-tight">
        {category && <IconChip category={category} size="sm" />}
        {title}
      </h2>
      {action && (
        <Link
          href={action.href}
          className="inline-flex items-center gap-1 rounded-md px-1 py-1.5 text-sm text-primary hover:underline"
        >
          {action.label}
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      )}
    </div>
  );
}

/** Small label for a metadata fact (type, year, status). Neutral by default. */
export function MetadataBadge({
  children,
  tone,
  icon: Icon,
}: {
  children: ReactNode;
  tone?: Tone;
  icon?: LucideIcon;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
        tone ? `tone-${tone} bg-[var(--tone-bg)] text-[var(--tone)]` : "bg-surface-2 text-muted"
      }`}
    >
      {Icon && <Icon size={12} aria-hidden="true" />}
      {children}
    </span>
  );
}

/**
 * Icon-led link card: one visual, one title, one optional line, one action.
 * `layout="row"` is the compact list form; the default stacks the icon above the text.
 */
export function FeatureCard({
  href,
  category,
  icon,
  tone,
  title,
  desc,
  meta,
  lead,
  layout = "stack",
}: {
  href: string;
  category?: CategoryName;
  icon?: LucideIcon;
  tone?: Tone;
  title: string;
  desc?: string;
  meta?: ReactNode;
  /** Replaces the icon chip, e.g. with a flag. */
  lead?: ReactNode;
  layout?: "stack" | "row";
}) {
  const t = tone ? `tone-${tone}` : "";
  return (
    <Link
      href={href}
      className={`card card-link prism-edge group flex gap-3 p-4 ${t} ${
        layout === "stack" ? "flex-col" : "items-center"
      }`}
    >
      {lead ?? <IconChip category={category} icon={icon} tone={tone} />}
      <span className="min-w-0 flex-1">
        <span className="block font-medium leading-snug">{title}</span>
        {desc && <span className="mt-0.5 line-clamp-2 block text-sm text-muted">{desc}</span>}
        {meta && <span className="mt-2 flex flex-wrap items-center gap-1.5">{meta}</span>}
      </span>
      <ArrowRight
        size={16}
        aria-hidden="true"
        className="shrink-0 self-center text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
      />
    </Link>
  );
}

export function CalculatorCard({
  href,
  slug,
  title,
  desc,
  tone = "violet",
}: {
  href: string;
  slug: string;
  title: string;
  desc?: string;
  tone?: Tone;
}) {
  return (
    <Link href={href} className="card card-link prism-edge group flex h-full flex-col gap-3 p-4">
      <span
        className={`tone-${tone} flex h-20 items-center justify-center rounded-lg bg-[var(--tone-bg)]`}
      >
        <CalcArt slug={slug} tone={tone} className="h-14 w-[4.5rem]" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-medium leading-snug">{title}</span>
        {desc && <span className="mt-0.5 line-clamp-2 block text-sm text-muted">{desc}</span>}
      </span>
      <span className="inline-flex items-center gap-1 text-sm text-primary">
        Open calculator
        <ArrowRight
          size={14}
          aria-hidden="true"
          className="transition-transform group-hover:translate-x-0.5"
        />
      </span>
    </Link>
  );
}

/** Document-style card for an externally hosted exam paper or study resource. */
export function DocumentCard({
  href,
  title,
  badges,
  source,
  note,
}: {
  href: string;
  title: string;
  badges: ReactNode;
  source: string;
  note?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer nofollow"
      className="card card-link tone-blue prism-edge group flex h-full gap-3 p-4"
    >
      <span className="relative flex h-16 w-12 shrink-0 items-center justify-center rounded-md border border-border bg-surface text-[var(--tone)] shadow-[3px_3px_0_var(--tone-bg)]">
        <FileText size={22} strokeWidth={1.5} aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-medium leading-snug">{title}</span>
        <span className="mt-0.5 block text-sm text-muted">{source}</span>
        <span className="mt-2 flex flex-wrap gap-1.5">{badges}</span>
        {note && <span className="mt-2 block text-xs text-muted">{note}</span>}
        <span className="mt-2 inline-flex items-center gap-1 text-sm text-primary">
          View paper <span className="sr-only">(opens external site)</span>
          <ArrowRight size={14} aria-hidden="true" />
        </span>
      </span>
    </a>
  );
}

/** Country header: flag, name, regulator, outline map and real catalogue figures. */
export function CountryHero({
  iso2,
  name,
  regulator,
  currency,
  productCount,
  universityCount,
}: {
  iso2: string;
  name: string;
  regulator?: string;
  currency?: string;
  productCount: number;
  universityCount?: number;
}) {
  const accent = flagAccent(iso2);
  return (
    <section className="glass relative overflow-hidden rounded-[var(--radius-xl)] p-5 sm:p-8">
      {accent && (
        <span
          aria-hidden="true"
          className="absolute inset-x-0 top-0 h-1"
          style={{ background: accent }}
        />
      )}
      <div className="grid items-center gap-6 md:grid-cols-[1fr_auto]">
        <div>
          <div className="flex items-center gap-4">
            <Flag iso2={iso2} name={name} className="h-12 w-[4.5rem]" />
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{name}</h1>
              {regulator && (
                <p className="mt-1 flex items-center gap-1.5 text-sm text-muted">
                  <Landmark size={14} aria-hidden="true" />
                  {regulator}
                </p>
              )}
            </div>
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-3 sm:max-w-md">
            <div className="card tone-teal p-3">
              <dt className="flex items-center gap-1.5 text-xs text-muted">
                <Pill size={14} aria-hidden="true" className="text-[var(--tone)]" />
                Products listed
              </dt>
              <dd className="mt-1 text-xl font-semibold">{productCount}</dd>
            </div>
            {universityCount !== undefined && (
              <Link
                href={`/universities?country=${iso2}`}
                className="card card-link tone-blue block p-3"
              >
                <dt className="flex items-center gap-1.5 text-xs text-muted">
                  <CategoryIcon category="universities" size={14} className="text-[var(--tone)]" />
                  Veterinary schools
                </dt>
                <dd className="mt-1 text-xl font-semibold">{universityCount}</dd>
              </Link>
            )}
            {currency && (
              <div className="card tone-amber p-3">
                <dt className="flex items-center gap-1.5 text-xs text-muted">
                  <Coins size={14} aria-hidden="true" className="text-[var(--tone)]" />
                  Price currency
                </dt>
                <dd className="mt-1 text-xl font-semibold">{currency}</dd>
              </div>
            )}
          </dl>
        </div>
        <figure className="mx-auto w-full max-w-[18rem] md:max-w-[22rem]">
          <CountryMap iso2={iso2} name={name} />
          <figcaption className="mt-1 text-center text-xs text-muted">
            Outline: Natural Earth, public domain.{" "}
            <Link href="/credits" className="underline">
              Credits
            </Link>
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
