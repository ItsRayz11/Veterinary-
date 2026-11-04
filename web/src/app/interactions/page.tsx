import { PageTitle } from "@/components/ui/visual";
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
      <PageTitle
        category="interactions"
        helpLabel="About the interaction checker"
        help="Only documented, reviewed interactions are shown. No matching interaction does not establish safety. Consult a veterinarian before combining medicines."
      >
        Interaction Checker
      </PageTitle>
      <Alert tone="warn">No interaction listed does not mean the combination is safe.</Alert>
      <InteractionChecker />
    </div>
  );
}
