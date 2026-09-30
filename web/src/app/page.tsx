import Link from "next/link";
import { SearchBox } from "@/components/search-box";

const TOOLS = [
  {
    href: "/calculators/dose-calculator",
    title: "Dose calculator",
    desc: "mg/kg to total mg and mL",
  },
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
