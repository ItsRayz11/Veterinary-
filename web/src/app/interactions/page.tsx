import type { Metadata } from "next";
import { InteractionChecker } from "@/components/interaction-checker";
import { Alert, Breadcrumbs } from "@/components/ui/primitives";

export const metadata: Metadata = {
  title: "Drug interaction checker",
  description: "Check reviewed interactions between veterinary drugs.",
  alternates: { canonical: "/interactions" },
};

export default function InteractionsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Interactions" }]} />
      <h1 className="text-2xl font-semibold">Interaction checker</h1>
      <Alert tone="warn" title="Only reviewed interactions are listed">
        No result does not mean a combination is safe. Check the product labels and a current
        reference.
      </Alert>
      <InteractionChecker />
    </div>
  );
}
