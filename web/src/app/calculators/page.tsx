import type { Metadata } from "next";
import Link from "next/link";
import { Breadcrumbs } from "@/components/ui/primitives";
import { CALCULATORS } from "@/lib/calc/registry";

export const metadata: Metadata = {
  title: "Calculators",
  description: "Veterinary dose, dilution, fluid, infusion, flock and withdrawal calculators.",
  alternates: { canonical: "/calculators" },
};

const ALL = [
  {
    href: "/calculators/dose-calculator",
    title: "Dose",
    desc: "mg/kg to total mg and mL",
  },
  ...CALCULATORS.map((c) => ({
    href: `/calculators/${c.slug}`,
    title: c.title,
    desc: c.description,
  })),
];

export default function CalculatorsIndex() {
  return (
    <main className="space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Calculators" }]} />
      <h1 className="text-2xl font-semibold">Calculators</h1>
      <ul className="grid gap-2 sm:grid-cols-2">
        {ALL.map((c) => (
          <li key={c.href}>
            <Link
              href={c.href}
              className="block h-full rounded-md border border-border bg-surface p-3 hover:border-primary"
            >
              <span className="font-medium">{c.title}</span>
              <span className="block text-sm text-muted">{c.desc}</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
