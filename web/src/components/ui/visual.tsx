import { HelpTip } from "./help-tip";
import Link from "next/link";
import { ArrowRight, FileText, Landmark, Coins, Pill } from "lucide-react";
import type { ReactNode } from "react";
import { CalcArt } from "./calc-art";
import { CountryMap } from "./country-map";
import { Flag, flagAccent } from "./flag";
import { CategoryIcon, IconChip, type CategoryName, type Tone } from "./icons";
import type { LucideIcon } from "lucide-react";

/** Page `h1` with a category icon chip, matching the detail-page headers. */
export function PageTitle({
  category,
  children,
  help,
  helpLabel = "About this page",
}: {
  category: CategoryName;
  children: ReactNode;
  /** Longer explanation, shown in a "(?)" popover instead of a paragraph under the title. */
  help?: ReactNode;
  helpLabel?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <IconChip category={category} size="md" />
      <h1 className="text-[32px] sm:text-[40px]">{children}</h1>
      {help && <HelpTip label={helpLabel}>{help}</HelpTip>}
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
              className="neo inline-flex min-h-10 items-center gap-2 rounded-[var(--radius-md)] px-3 text-sm"
            >
              <CategoryIcon category={i.category} size={16} className="text-muted" />
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
  action,
}: {
  id: string;
  title: string;
  action?: { href: string; label: string };
}) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <h2 id={id} className="text-lg font-medium">
        {title}
      </h2>
      {action && (
        <Link
          href={action.href}
          className="inline-flex min-h-11 shrink-0 items-center gap-1 text-sm text-primary underline-offset-4 hover:underline"
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
      className={`inline-flex items-center gap-1 rounded-[var(--radius-sm)] px-2 py-0.5 text-xs font-medium ${
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
      className={`card card-link group flex gap-4 p-4 sm:p-5 ${t} ${
        layout === "stack" ? "flex-col" : "items-center"
      }`}
    >
      {lead ?? <IconChip category={category} icon={icon} tone={tone} />}
      <span className="min-w-0 flex-1">
        <span className="block font-medium leading-snug">{title}</span>
        {desc && <span className="mt-0.5 line-clamp-2 text-sm text-muted">{desc}</span>}
        {meta && <span className="mt-2 flex flex-wrap items-center gap-1.5">{meta}</span>}
      </span>
      <ArrowRight
        size={16}
        aria-hidden="true"
        className="shrink-0 self-center text-muted transition-[color,transform] duration-150 group-hover:translate-x-0.5 group-hover:text-primary"
      />
    </Link>
  );
}

export function CalculatorCard({
  href,
  slug,
  title,
  desc,
}: {
  href: string;
  slug: string;
  title: string;
  desc?: string;
}) {
  return (
    // A compact row on phones (the list stays scannable), the illustrated tile from sm up.
    <Link
      href={href}
      className="card card-link group flex h-full items-center gap-4 p-4 sm:flex-col sm:items-stretch"
    >
      <span className="flex size-16 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-surface-2 sm:h-24 sm:w-auto">
        <CalcArt slug={slug} className="h-10 w-14 sm:h-14 sm:w-[4.5rem]" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-medium leading-snug">{title}</span>
        {desc && <span className="mt-0.5 line-clamp-2 text-sm text-muted">{desc}</span>}
      </span>
      <ArrowRight size={16} aria-hidden="true" className="shrink-0 text-muted sm:hidden" />
      <span className="hidden items-center gap-1 text-sm text-primary sm:inline-flex">
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
      className="card card-link tone-blue group flex h-full gap-4 p-4 sm:p-5"
    >
      <span className="relative flex h-16 w-12 shrink-0 items-center justify-center rounded-md border border-border bg-surface text-[var(--tone)] shadow-[3px_3px_0_var(--surface-2)]">
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
              <h1 className="text-[32px] sm:text-[40px]">{name}</h1>
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
                <Pill size={14} aria-hidden="true" className="text-muted" />
                Products listed
              </dt>
              <dd className="mt-1 text-2xl font-medium tabular-nums">{productCount}</dd>
            </div>
            {universityCount !== undefined && (
              <div className="card card-link tone-blue relative p-3">
                <dt className="flex items-center gap-1.5 text-xs text-muted">
                  <CategoryIcon category="universities" size={14} className="text-muted" />
                  Veterinary schools
                </dt>
                <dd className="mt-1 text-2xl font-medium tabular-nums">
                  <Link
                    href={`/universities?country=${iso2}`}
                    className="after:absolute after:inset-0 after:content-['']"
                  >
                    {universityCount}
                    <span className="sr-only"> veterinary schools, view list</span>
                  </Link>
                </dd>
              </div>
            )}
            {currency && (
              <div className="card tone-amber p-3">
                <dt className="flex items-center gap-1.5 text-xs text-muted">
                  <Coins size={14} aria-hidden="true" className="text-muted" />
                  Price currency
                </dt>
                <dd className="mt-1 text-2xl font-medium tabular-nums">{currency}</dd>
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
