"use client";

import { useEffect } from "react";
import { reportError } from "@/lib/report-error";

/** Last resort when the root layout itself fails: plain HTML, no app components. */
export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    reportError(error, "Global error");
  }, [error]);
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: "32rem" }}>
        <h1>Something went wrong</h1>
        <p>The page could not be displayed. Nothing you entered has been lost on our side.</p>
        <button type="button" onClick={reset} style={{ padding: "0.6rem 1rem" }}>
          Try again
        </button>
      </body>
    </html>
  );
}
