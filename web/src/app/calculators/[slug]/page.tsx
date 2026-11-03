import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { GenericCalculator } from "@/components/generic-calculator";
import { CalcArt } from "@/components/ui/calc-art";
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
    <div className="mx-auto max-w-2xl space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Calculators", href: "/calculators" },
          { label: def.title },
        ]}
      />
      <div className="flex items-center gap-4">
        <span className="tone-violet flex h-16 w-20 shrink-0 items-center justify-center rounded-xl bg-[var(--tone-bg)]">
          <CalcArt slug={def.slug} className="h-12 w-16" />
        </span>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{def.title}</h1>
          <p className="mt-1 text-sm text-muted">{def.description}</p>
        </div>
      </div>
      <Alert tone="warn" title="Decision support only">
        The calculator does arithmetic on the values you enter. It does not choose a drug, dose or
        rate. Confirm every value against its source and the product label.
      </Alert>
      <GenericCalculator slug={def.slug} />
    </div>
  );
}
