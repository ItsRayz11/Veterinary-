import Link from "next/link";
import { SearchBox } from "@/components/search-box";
import { Tile } from "@/components/ui/primitives";
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

const TOOLS = [
  {
    href: "/calculators/dose-calculator",
    title: "Dose calculator",
    desc: "mg/kg to total mg and mL",
    wide: true,
  },
  { href: "/interactions", title: "Interaction checker", desc: "Reviewed drug-drug interactions" },
  {
    href: "/ask",
    title: "Ask the reference",
    desc: "Answers only from reviewed records, with citations",
  },
  {
    href: "/calculators",
    title: "All calculators",
    desc: "Dilution, fluids, infusion, CRI, flock water dose, withdrawal date",
    full: true,
  },
];

const LEARN = [
  { href: "/study", title: "Study", desc: "Mock exams from reviewed questions" },
  { href: "/jobs", title: "Jobs", desc: "Moderated veterinary job listings" },
  { href: "/scholarships", title: "Scholarships", desc: "Moderated scholarship listings" },
];

/** A homepage block must never take the page down when the data service is unavailable. */
async function safeGet<T>(path: string): Promise<T[]> {
  try {
    return await apiGet<T[]>(path);
  } catch {
    return [];
  }
}

function SectionHeading({ id, children }: { id: string; children: string }) {
  return (
    <h2 id={id} className="mb-3 text-sm font-medium uppercase tracking-wide text-muted">
      {children}
    </h2>
  );
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
          <SectionHeading id="species-h">Browse by species</SectionHeading>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {topSpecies.map((s) => (
              <li key={s.slug}>
                <Tile href={`/species/${s.slug}`} title={s.name} />
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
        <SectionHeading id="tools-h">Clinical tools</SectionHeading>
        <ul className="bento">
          {TOOLS.map((t) => (
            <li key={t.href} className={t.full ? "bento-full" : t.wide ? "bento-wide" : ""}>
              <Tile href={t.href} title={t.title} desc={t.desc} />
            </li>
          ))}
        </ul>
      </section>

      {countries.length > 0 && (
        <section aria-labelledby="countries-h">
          <SectionHeading id="countries-h">Country catalogues</SectionHeading>
          <ul className="flex flex-wrap gap-3 text-sm">
            {countries.map((c) => (
              <li key={c.iso2}>
                <Link
                  href={`/countries/${c.iso2}`}
                  className="neo inline-block rounded-full px-4 py-2"
                >
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="learn-h">
        <SectionHeading id="learn-h">Study and careers</SectionHeading>
        <ul className="grid gap-3 sm:grid-cols-3">
          {LEARN.map((t) => (
            <li key={t.href}>
              <Tile href={t.href} title={t.title} desc={t.desc} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
