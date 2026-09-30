"use client";

import { useEffect } from "react";
import { reportError } from "@/lib/report-error";

/** Reports uncaught errors and unhandled promise rejections from any page. */
export function ErrorReporter() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    const onError = (e: ErrorEvent) => reportError(e.error ?? e.message);
    const onRejection = (e: PromiseRejectionEvent) => reportError(e.reason, "Unhandled rejection");
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);
  return null;
}
