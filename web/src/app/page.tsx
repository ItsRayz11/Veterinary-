import Link from "next/link";
import { SearchBox } from "@/components/search-box";
import { Flag } from "@/components/ui/flag";
import { speciesIcon, type CategoryName } from "@/components/ui/icons";
import { FeatureCard, SectionHeader } from "@/components/ui/visual";
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

const TOOLS: {
  href: string;
  title: string;
  desc: string;
  category: CategoryName;
  wide?: boolean;
  full?: boolean;
}[] = [
  {
    href: "/calculators/dose-calculator",
    title: "Dose calculator",
    desc: "mg/kg to total mg and mL",
    category: "medicines",
    wide: true,
  },
  {
    href: "/interactions",
    title: "Interaction checker",
    desc: "Reviewed drug-drug interactions",
    category: "interactions",
  },
  {
    href: "/ask",
    title: "Ask the reference",
    desc: "Answers only from reviewed records, with citations",
    category: "ask",
  },
  {
    href: "/calculators",
    title: "All calculators",
    desc: "Dilution, fluids, infusion, CRI, flock water dose, withdrawal date",
    category: "calculators",
    full: true,
  },
];

const LEARN: { href: string; title: string; desc: string; category: CategoryName }[] = [
  {
    href: "/study",
    title: "Study",
    desc: "Mock exams from reviewed questions",
    category: "mocktests",
  },
  { href: "/jobs", title: "Jobs", desc: "Moderated veterinary job listings", category: "jobs" },
  {
    href: "/scholarships",
    title: "Scholarships",
    desc: "Moderated scholarship listings",
    category: "scholarships",
  },
];

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

  return (
    <div className="mx-auto max-w-4xl space-y-10 pt-4">
      <section className="glass space-y-4 rounded-[var(--radius-xl)] p-5 sm:p-10">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Veterinary drug reference
        </h1>
        <p className="max-w-2xl text-sm text-muted sm:text-base">
          Generics, brands and manufacturers, with sources and review status on every clinical
          statement.
        </p>
        <div className="max-w-2xl">
          <SearchBox />
        </div>
        <p className="text-xs text-muted">
          Records marked as imported have not been clinically reviewed. Only reviewed statements
          carry a verified label.
        </p>
      </section>

      {topSpecies.length > 0 && (
        <section aria-labelledby="species-h">
          <SectionHeader
            id="species-h"
            title="Browse by species"
            category="species"
            action={{ href: "/species", label: "All species" }}
          />
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {topSpecies.map((s) => (
              <li key={s.slug}>
                <FeatureCard
                  layout="row"
                  href={`/species/${s.slug}`}
                  icon={speciesIcon(s.slug + " " + s.name)}
                  category="species"
                  title={s.name}
                />
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm">
            <Link href="/classes" className="text-primary underline">
              Browse by drug class
            </Link>
          </p>
        </section>
      )}

      <section aria-labelledby="tools-h">
        <SectionHeader id="tools-h" title="Clinical tools" category="calculators" />
        <ul className="bento">
          {TOOLS.map((t) => (
            <li key={t.href} className={t.full ? "bento-full" : t.wide ? "bento-wide" : ""}>
              <FeatureCard
                layout="row"
                href={t.href}
                category={t.category}
                title={t.title}
                desc={t.desc}
              />
            </li>
          ))}
        </ul>
      </section>

      {countries.length > 0 && (
        <section aria-labelledby="countries-h">
          <SectionHeader
            id="countries-h"
            title="Country catalogues"
            category="countries"
            action={{ href: "/countries", label: "All countries" }}
          />
          <ul className="flex flex-wrap gap-3 text-sm">
            {countries.map((c) => (
              <li key={c.iso2}>
                <Link
                  href={`/countries/${c.iso2}`}
                  className="neo inline-flex items-center gap-2 rounded-full px-4 py-2"
                >
                  <Flag iso2={c.iso2} className="h-4 w-6 text-[10px]" />
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="learn-h">
        <SectionHeader id="learn-h" title="Study and careers" category="study" />
        <ul className="grid gap-3 sm:grid-cols-3">
          {LEARN.map((t) => (
            <li key={t.href}>
              <FeatureCard
                layout="row"
                href={t.href}
                category={t.category}
                title={t.title}
                desc={t.desc}
              />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
