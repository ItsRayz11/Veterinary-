import type { Metadata } from "next";
import { Breadcrumbs, PageHeader } from "@/components/ui/primitives";
import { CalculatorCard } from "@/components/ui/visual";
import { CALCULATORS } from "@/lib/calc/registry";

export const metadata: Metadata = {
  title: "Calculators",
  description: "Veterinary dose, dilution, fluid, infusion, flock and withdrawal calculators.",
  alternates: { canonical: "/calculators" },
};

const ALL = [
  {
    href: "/calculators/dose-calculator",
    slug: "dose-calculator",
    title: "Dose",
    desc: "mg/kg to total mg and mL",
  },
  ...CALCULATORS.map((c) => ({
    href: `/calculators/${c.slug}`,
    slug: c.slug,
    title: c.title,
    desc: c.description,
  })),
];

export default function CalculatorsIndex() {
  return (
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Calculators" }]} />
      <PageHeader
        title="Calculators"
        lead="Deterministic calculations. Check every result against the product label."
      />
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {ALL.map((c) => (
          <li key={c.href}>
            <CalculatorCard
              href={c.href}
              slug={c.slug}
              title={c.title}
              desc={c.desc}
              tone={
                c.slug === "withdrawal-date"
                  ? "amber"
                  : c.slug === "dose-calculator"
                    ? "teal"
                    : "violet"
              }
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
