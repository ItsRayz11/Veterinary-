import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { GenericCalculator } from "@/components/generic-calculator";
import { Alert, Breadcrumbs } from "@/components/ui/primitives";
import { CALCULATORS, bySlug } from "@/lib/calc/registry";

export const dynamicParams = false;

export function generateStaticParams() {
  return CALCULATORS.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: PageProps<"/calculators/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const def = bySlug(slug);
  if (!def) return {};
  return {
    title: def.title,
    description: def.description,
    alternates: { canonical: `/calculators/${def.slug}` },
  };
}

export default async function CalculatorPage({ params }: PageProps<"/calculators/[slug]">) {
  const { slug } = await params;
  const def = bySlug(slug);
  if (!def) notFound();
  return (
    <main className="mx-auto max-w-2xl space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Calculators", href: "/calculators" },
          { label: def.title },
        ]}
      />
      <h1 className="text-2xl font-semibold">{def.title}</h1>
      <p className="text-sm text-muted">{def.description}</p>
      <Alert tone="warn" title="Decision support only">
        The calculator does arithmetic on the values you enter. It does not choose a drug, dose or
        rate. Confirm every value against its source and the product label.
      </Alert>
      <GenericCalculator slug={def.slug} />
    </main>
  );
}
