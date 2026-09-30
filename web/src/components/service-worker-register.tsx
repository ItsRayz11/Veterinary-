"use client";

import { useEffect } from "react";
import { CALCULATORS } from "@/lib/calc/registry";

/** Registers the service worker in production and asks it to keep the calculators offline. */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    let cancelled = false;
    navigator.serviceWorker
      .register("/sw.js", { scope: "/", updateViaCache: "none" })
      .then(() => navigator.serviceWorker.ready)
      .then((reg) => {
        if (cancelled) return;
        reg.active?.postMessage({
          type: "PRECACHE",
          urls: ["/calculators", "/calculators/dose-calculator"].concat(
            CALCULATORS.map((c) => `/calculators/${c.slug}`),
          ),
        });
      })
      .catch(() => {
        // Offline support is an enhancement; the site works without it.
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return null;
}
