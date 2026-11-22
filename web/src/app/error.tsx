"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Alert } from "@/components/ui/primitives";
import { reportError } from "@/lib/report-error";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Expected "service unreachable" states are not bugs in our code; everything else is reported.
    if (!error.message.includes("unreachable"))
      reportError(
        error,
        error.digest ? `Page error (server digest ${error.digest})` : "Page error",
      );
  }, [error]);
  return (
    <div className="mx-auto max-w-xl space-y-3 pt-8">
      <Alert tone="danger" title="Something went wrong">
        {/* Next.js hides the real message of a server error in production builds, so this text has to
            be useful on its own: say the likely cause and what to do (no claim about unsaved input: this page cannot know). */}
        {error.message.includes("unreachable")
          ? "The data service is currently unreachable. Please try again shortly."
          : "This page could not be loaded. The data service may be temporarily unavailable. Please try again in a moment."}
      </Alert>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={reset}
          className="neo inline-flex min-h-11 items-center rounded-lg px-4 text-sm font-medium"
        >
          Try again
        </button>
        <Link
          href="/"
          className="inline-flex min-h-11 items-center rounded-lg px-3 text-sm underline"
        >
          Go to the home page
        </Link>
      </div>
    </div>
  );
}
