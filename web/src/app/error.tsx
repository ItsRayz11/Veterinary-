"use client";

import { useEffect } from "react";
import { Alert } from "@/components/ui/primitives";
import { reportError } from "@/lib/report-error";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    // Expected "service unreachable" states are not bugs in our code; everything else is reported.
    if (!error.message.includes("unreachable")) reportError(error, "Page error");
  }, [error]);
  return (
    <div className="mx-auto max-w-xl space-y-3 pt-8">
      <Alert tone="danger" title="Something went wrong">
        {error.message.includes("unreachable")
          ? "The data service is currently unreachable. Nothing has been lost; please try again shortly."
          : "This page could not be loaded."}
      </Alert>
      <button
        type="button"
        onClick={reset}
        className="rounded-md border border-border bg-surface px-3 py-2 text-sm"
      >
        Try again
      </button>
    </div>
  );
}
