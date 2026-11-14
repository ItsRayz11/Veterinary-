"use client";

import { createContext, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";
import type { AdsConfig, AdZone } from "@/lib/ads";

type Consent = "unknown" | "granted" | "denied";
const KEY = "vetref-ad-consent";

const Ctx = createContext<{ config: AdsConfig; consent: Consent; set: (c: Consent) => void }>({
  config: { enabled: false, client: "", slots: {} },
  consent: "unknown",
  set: () => {},
});

function readConsent(): Consent {
  try {
    const v = localStorage.getItem(KEY);
    return v === "granted" || v === "denied" ? v : "unknown";
  } catch {
    return "unknown";
  }
}

/** Consent is asked only when ads are configured. Nothing from an ad network loads before the
 *  visitor accepts, and "Reject" keeps the site fully usable without any ads. */
const listeners = new Set<() => void>();
function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}
let memory: Consent | null = null; // used when storage is unavailable (private mode)

export function AdsProvider({ config, children }: { config: AdsConfig; children: ReactNode }) {
  const consent = useSyncExternalStore<Consent>(
    subscribe,
    () => memory ?? readConsent(),
    () => "unknown",
  );
  const set = (c: Consent) => {
    memory = c;
    try {
      localStorage.setItem(KEY, c);
    } catch {
      // the choice lasts for this page view only
    }
    listeners.forEach((l) => l());
  };
  return (
    <Ctx.Provider value={{ config, consent, set }}>
      {children}
      {config.enabled && consent === "unknown" && <ConsentBanner />}
    </Ctx.Provider>
  );
}

function ConsentBanner() {
  const { set } = useContext(Ctx);
  return (
    <div
      role="region"
      aria-label="Advertising choices"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface p-4 text-sm shadow-lg"
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-3 sm:flex-row sm:items-center">
        <p className="flex-1">
          VetRef shows clearly labelled adverts outside clinical and regulatory information. They
          may use cookies. Adverts never change the content. You can decline and still use
          everything.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => set("denied")}
            className="min-h-11 rounded-md border border-border px-4"
          >
            Decline
          </button>
          <button
            type="button"
            onClick={() => set("granted")}
            className="min-h-11 rounded-md bg-primary px-4 text-white"
          >
            Allow adverts
          </button>
        </div>
      </div>
    </div>
  );
}

let scriptRequested = false;
function loadScript(client: string) {
  if (scriptRequested) return;
  scriptRequested = true;
  const s = document.createElement("script");
  s.async = true;
  s.crossOrigin = "anonymous";
  s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(client)}`;
  document.head.appendChild(s);
}

/** A labelled advertisement. Renders nothing (no space, no request) unless ads are enabled, the
 *  visitor consented, and a slot id exists for the zone. The zone type has no clinical value, so
 *  an advert cannot be placed beside doses, withdrawal periods, interactions or registrations. */
export function AdSlot({ zone }: { zone: AdZone }) {
  const { config, consent } = useContext(Ctx);
  const slot = config.slots[zone];
  const active = config.enabled && consent === "granted" && !!slot;
  useEffect(() => {
    if (!active) return;
    loadScript(config.client);
    try {
      const w = window as unknown as { adsbygoogle?: unknown[] };
      (w.adsbygoogle = w.adsbygoogle || []).push({});
    } catch {
      // the ad network failed to load; the page is unaffected
    }
  }, [active, config.client]);
  if (!active) return null;
  return (
    <aside aria-label="Advertisement" className="my-6 rounded-md border border-border p-2">
      <p className="mb-1 text-xs text-muted">Advertisement</p>
      <ins
        className="adsbygoogle block min-h-[100px]"
        data-ad-client={config.client}
        data-ad-slot={slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </aside>
  );
}
