import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";
import { SearchBox } from "@/components/search-box";
import { CalcArt } from "@/components/ui/calc-art";
import { Flag } from "@/components/ui/flag";
import { CategoryIcon, type CategoryName } from "@/components/ui/icons";
import { SpeciesPhoto, speciesCredit } from "@/components/ui/species-photo";
import { SectionHeader } from "@/components/ui/visual";
import { apiGet } from "@/lib/api";

export const dynamic = "force-dynamic";

interface SpeciesRow {
  slug: string;
  name: string;
  parent: string | null;
}

interface CountryRow {
  iso2: string;
  name: string;
  currency: string;
}

const TOOLS: { href: string; title: string; desc: string; category: CategoryName }[] = [
  {
    href: "/interactions",
    title: "Interaction checker",
    desc: "Reviewed drug-drug interactions",
    category: "interactions",
  },
  {
    href: "/ask",
    title: "Ask the reference",
    desc: "Answers from reviewed records, with citations",
    category: "ask",
  },
  {
    href: "/calculators",
    title: "All calculators",
    desc: "Dilution, fluids, infusion, CRI, flock water dose, withdrawal date",
    category: "calculators",
  },
];

const LEARN: { href: string; title: string; desc: string; category: CategoryName }[] = [
  {
    href: "/study",
    title: "Study",
    desc: "Mock exams from reviewed questions",
    category: "mocktests",
  },
  {
    href: "/universities",
    title: "Universities",
    desc: "Veterinary schools by country",
    category: "universities",
  },
  { href: "/jobs", title: "Jobs", desc: "Moderated job listings", category: "jobs" },
  {
    href: "/scholarships",
    title: "Scholarships",
    desc: "Moderated scholarship listings",
    category: "scholarships",
  },
];

/** Species shown in the hero plate, in this order, when the catalogue has them and a photo exists. */
const PLATE_ORDER = ["cattle", "dog", "cat", "poultry", "horse", "sheep", "goat"];

/** A homepage block must never take the page down when the data service is unavailable. */
async function safeGet<T>(path: string): Promise<T[]> {
  try {
    return await apiGet<T[]>(path);
  } catch {
    return [];
  }
}

export default async function Home() {
  const [species, countries] = await Promise.all([
    safeGet<SpeciesRow>("/species/"),
    safeGet<CountryRow>("/countries/"),
  ]);
  const topSpecies = species.filter((s) => !s.parent);
  const plate = PLATE_ORDER.map((slug) => topSpecies.find((s) => s.slug === slug))
    .filter((s): s is SpeciesRow => !!s && !!speciesCredit(s.slug))
    .slice(0, 3);
  const hasPlate = plate.length === 3;

  return (
    <div className="space-y-16 sm:space-y-20">
      <section
        aria-labelledby="hero-h"
        className={`grid items-center gap-10 pt-4 sm:pt-10 lg:gap-14 ${
          hasPlate ? "lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]" : ""
        }`}
      >
        <div className="rise max-w-xl space-y-6">
          <h1 id="hero-h" className="text-[40px] sm:text-[56px] lg:text-[64px]">
            Veterinary drug reference
          </h1>
          <p className="text-lg leading-8 text-text-2">
            Generics, brands and manufacturers by country, with the source and review status of
            every clinical statement.
          </p>
          <SearchBox />
          <p className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted">
            <span className="inline-flex items-center gap-2">
              <span className="review-mark text-ok" aria-hidden="true" />
              Clinically reviewed
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="review-mark text-warn" data-reviewed="false" aria-hidden="true" />
              Imported, not yet reviewed
            </span>
          </p>
        </div>

        {hasPlate && (
          <ul
            aria-label="Browse by species"
            className="plate-in grid grid-cols-3 gap-2 sm:gap-3 lg:grid-cols-2 lg:grid-rows-2"
          >
            {plate.map((s, i) => (
              <li
                key={s.slug}
                style={{ "--i": i } as CSSProperties}
                className={i === 0 ? "lg:row-span-2" : ""}
              >
                <Link
                  href={`/species/${s.slug}`}
                  className="card-link relative block h-full overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface-2"
                >
                  <SpeciesPhoto
                    slug={s.slug}
                    name={s.name}
                    priority={i === 0}
                    sizes="(min-width: 1024px) 28vw, 33vw"
                    className={`aspect-[3/4] h-full ${
                      i === 0 ? "lg:aspect-auto" : "lg:aspect-[4/3]"
                    }`}
                  />
                  <span className="absolute bottom-2 left-2 inline-flex items-center gap-1 rounded-[var(--radius-sm)] bg-surface px-2 py-1 text-xs font-medium text-text shadow-[var(--shadow-sm)] sm:bottom-3 sm:left-3 sm:text-sm">
                    {s.name}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="tools-h">
        <SectionHeader id="tools-h" title="Clinical tools" />
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
          <Link
            href="/calculators/dose-calculator"
            className="card card-link group flex flex-col justify-between gap-8 p-5 sm:p-6"
          >
            <span className="flex items-start justify-between gap-4">
              <span>
                <span className="block text-lg font-medium">Dose calculator</span>
                <span className="mt-1 block text-sm text-muted">
                  From a dose rate and body weight to total mg and mL
                </span>
              </span>
              <CalcArt slug="dose-calculator" className="h-12 w-16" />
            </span>
            {/* The arithmetic the calculator performs. Units only: no dose values are shown. */}
            <span
              aria-label="Dose rate in milligrams per kilogram times body weight in kilograms gives total milligrams; divided by concentration in milligrams per millilitre gives millilitres"
              className="grid grid-cols-[auto_1fr] items-baseline gap-x-4 gap-y-2 rounded-[var(--radius-md)] bg-surface-2 px-4 py-4 font-mono text-sm text-text-2 sm:text-[15px]"
            >
              <span aria-hidden="true" className="text-muted">
                Total
              </span>
              <span aria-hidden="true">
                mg/kg × kg = <span className="text-text">mg</span>
              </span>
              <span aria-hidden="true" className="text-muted">
                Volume
              </span>
              <span aria-hidden="true">
                mg ÷ mg/mL = <span className="text-primary">mL</span>
              </span>
            </span>
            <span className="inline-flex items-center gap-1 text-sm font-medium text-primary">
              Open dose calculator
              <ArrowRight
                size={16}
                aria-hidden="true"
                className="transition-transform duration-150 group-hover:translate-x-0.5"
              />
            </span>
          </Link>
          <ul className="card divide-y divide-border overflow-hidden">
            {TOOLS.map((t) => (
              <li key={t.href}>
                <Link
                  href={t.href}
                  className="group flex items-center gap-4 px-5 py-4 transition-colors hover:bg-surface-2"
                >
                  <span className="icon-chip size-10 rounded-[var(--radius-md)]" aria-hidden="true">
                    <CategoryIcon category={t.category} size={18} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{t.title}</span>
                    <span className="block text-sm text-muted">{t.desc}</span>
                  </span>
                  <ArrowRight
                    size={16}
                    aria-hidden="true"
                    className="shrink-0 text-muted transition-[color,transform] duration-150 group-hover:translate-x-0.5 group-hover:text-primary"
                  />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {topSpecies.length > 0 && (
        <section aria-labelledby="species-h">
          <SectionHeader
            id="species-h"
            title="Browse by species"
            action={{ href: "/classes", label: "Browse by drug class" }}
          />
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-4">
            {topSpecies.map((s) => (
              <li key={s.slug}>
                <Link
                  href={`/species/${s.slug}`}
                  className="card card-link flex items-center gap-3 p-2 pr-3"
                >
                  <SpeciesPhoto
                    slug={s.slug}
                    name=""
                    sizes="56px"
                    className="size-12 shrink-0 rounded-[var(--radius-sm)] sm:size-14"
                  />
                  <span className="min-w-0 truncate font-medium">{s.name}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {countries.length > 0 && (
        <section aria-labelledby="countries-h">
          <SectionHeader
            id="countries-h"
            title="Country catalogues"
            action={{ href: "/countries", label: "All countries" }}
          />
          <ul className="grid gap-2 sm:grid-cols-2 sm:gap-3 lg:grid-cols-3">
            {countries.map((c) => (
              <li key={c.iso2}>
                <Link
                  href={`/countries/${c.iso2}`}
                  className="card card-link flex min-h-14 items-center gap-3 px-4"
                >
                  <Flag iso2={c.iso2} className="h-4 w-6 shrink-0 rounded-[2px]" />
                  <span className="min-w-0 flex-1 truncate">{c.name}</span>
                  {c.currency && <span className="font-mono text-xs text-muted">{c.currency}</span>}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="learn-h">
        <SectionHeader id="learn-h" title="Study and careers" />
        <ul className="grid gap-2 sm:grid-cols-2 sm:gap-3">
          {LEARN.map((t) => (
            <li key={t.href}>
              <Link href={t.href} className="card card-link group flex items-center gap-4 p-4">
                <span className="icon-chip size-10 rounded-[var(--radius-md)]" aria-hidden="true">
                  <CategoryIcon category={t.category} size={18} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{t.title}</span>
                  <span className="block text-sm text-muted">{t.desc}</span>
                </span>
                <ArrowRight
                  size={16}
                  aria-hidden="true"
                  className="shrink-0 text-muted transition-[color,transform] duration-150 group-hover:translate-x-0.5 group-hover:text-primary"
                />
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
