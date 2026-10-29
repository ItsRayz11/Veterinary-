import type { Metadata } from "next";
import { Breadcrumbs, PageHeader, Tile } from "@/components/ui/primitives";
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
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Calculators" }]} />
      <PageHeader
        title="Calculators"
        lead="Deterministic calculations. Check every result against the product label."
      />
      <ul className="bento">
        {ALL.map((c, i) => (
          <li key={c.href} className={i === 0 ? "bento-wide" : ""}>
            <Tile href={c.href} title={c.title} desc={c.desc} />
          </li>
        ))}
      </ul>
    </div>
  );
}
