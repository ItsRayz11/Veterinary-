import type { Metadata } from "next";
import { AskAssistant } from "@/components/ask-assistant";
import { Alert } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Ask the reference", robots: { index: false } };

export default function AskPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">Ask the reference</h1>
      <Alert tone="warn" title="Reviewed records only">
        Answers are generated only from reviewed records, must cite them, and are discarded if they
        contain any number that is not in those records. This is not clinical advice.
      </Alert>
      <AskAssistant />
    </div>
  );
}
