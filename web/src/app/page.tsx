import Link from "next/link";
import { SearchBox } from "@/components/search-box";

const TOOLS = [
  {
    href: "/calculators/dose-calculator",
    title: "Dose calculator",
    desc: "mg/kg to total mg and mL",
  },
  {
    href: "/calculators",
    title: "All calculators",
    desc: "Dilution, fluids, infusion, CRI, flock water dose, withdrawal date",
  },
  { href: "/interactions", title: "Interaction checker", desc: "Reviewed drug-drug interactions" },
  {
    href: "/ask",
    title: "Ask the reference",
    desc: "Answers only from reviewed records, with citations",
  },
  { href: "/study", title: "Study", desc: "Mock exams from reviewed questions" },
];

const BROWSE = [
  { href: "/species", title: "Species" },
  { href: "/classes", title: "Drug classes" },
  { href: "/countries", title: "Countries" },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl space-y-8 pt-6">
      <div className="space-y-3">
        <h1 className="text-xl font-semibold">Veterinary drug reference</h1>
        <SearchBox />
        <p className="text-sm text-muted">
          Generics, brands and manufacturers, with sources and review status on every clinical
          statement.
        </p>
      </div>
      <nav aria-label="Browse" className="flex flex-wrap gap-2 text-sm">
        {BROWSE.map((b) => (
          <Link
            key={b.href}
            href={b.href}
            className="rounded-full border border-border bg-surface px-3 py-2 hover:border-primary"
          >
            Browse by {b.title.toLowerCase()}
          </Link>
        ))}
      </nav>
      <section aria-labelledby="tools-h">
        <h2 id="tools-h" className="mb-2 text-sm font-medium uppercase tracking-wide text-muted">
          Clinical tools
        </h2>
        <ul className="grid gap-2 sm:grid-cols-2">
          {TOOLS.map((t) => (
            <li key={t.href}>
              <Link
                href={t.href}
                className="block rounded-md border border-border bg-surface p-3 hover:border-primary"
              >
                <span className="font-medium">{t.title}</span>
                <span className="block text-sm text-muted">{t.desc}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
