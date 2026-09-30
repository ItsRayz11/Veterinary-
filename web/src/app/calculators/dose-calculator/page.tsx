import type { Metadata } from "next";
import { DoseCalculator } from "@/components/dose-calculator";
import { Alert, Breadcrumbs } from "@/components/ui/primitives";

export const metadata: Metadata = {
  title: "Dose calculator",
  description: "Calculate total mg and mL from body weight, mg/kg dose and product concentration.",
  alternates: { canonical: "/calculators/dose-calculator" },
};

const num = (v: string | string[] | undefined) =>
  typeof v === "string" && /^\d+(\.\d+)?$/.test(v) ? v : "";

export default async function Page({ searchParams }: PageProps<"/calculators/dose-calculator">) {
  const sp = await searchParams;
  const label = typeof sp.label === "string" ? sp.label.slice(0, 120) : "";
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Breadcrumbs
        items={[{ label: "Home", href: "/" }, { label: "Calculators" }, { label: "Dose" }]}
      />
      <h1 className="text-2xl font-semibold">Dose calculator</h1>
      <Alert tone="warn" title="Decision support only">
        The calculator does simple arithmetic on the values you enter. It does not choose a drug or
        dose. Confirm every dose against the source and the product label.
      </Alert>
      <DoseCalculator
        presetDose={num(sp.dose)}
        presetDoseMax={num(sp.dose_max)}
        presetLabel={num(sp.dose) ? label : ""}
      />
    </div>
  );
}
