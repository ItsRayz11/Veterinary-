"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { startsNavigation } from "@/lib/navigation-click";

/** Give up (and stop showing progress) if a navigation never completes, for example after an error. */
const GIVE_UP_MS = 15_000;
/** Announce to assistive technology only when the wait is long enough to matter. */
const ANNOUNCE_AFTER_MS = 400;

/**
 * Immediate feedback for slow navigations. Pages that read from the API are rendered on the server,
 * so after a tap the old page stays on screen until the new one is ready; on a slow connection that
 * looks like a dead button. This shows a thin progress bar (fades in after 120 ms, so fast
 * navigations never flash it) and a polite "Loading page" status until the URL changes.
 *
 * It only listens to clicks: it does not touch routing or the server response, so real HTTP status
 * codes (404 for unknown records, 5xx on outages) are unchanged.
 */
export function NavigationProgress() {
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const here = `${pathname}?${search}`;

  // The URL at which a navigation started. Pending ends by itself once the URL differs, so no
  // state needs resetting in an effect.
  const [startedFrom, setStartedFrom] = useState<string | null>(null);
  const [announcedFor, setAnnouncedFor] = useState<string | null>(null);
  const pending = startedFrom !== null && startedFrom === here;

  useEffect(() => {
    function onClick(e: MouseEvent) {
      const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!a) return;
      const link = { href: a.href, target: a.target, hasDownload: a.hasAttribute("download") };
      if (startsNavigation(e, link, window.location.href)) setStartedFrom(here);
    }
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [here]);

  useEffect(() => {
    if (!pending) return;
    const announce = setTimeout(() => setAnnouncedFor(here), ANNOUNCE_AFTER_MS);
    const giveUp = setTimeout(() => setStartedFrom(null), GIVE_UP_MS);
    return () => {
      clearTimeout(announce);
      clearTimeout(giveUp);
    };
  }, [pending, here]);

  return (
    <>
      {pending && <div aria-hidden="true" data-testid="nav-progress" className="nav-progress" />}
      <div role="status" className="sr-only">
        {pending && announcedFor === here ? "Loading page…" : ""}
      </div>
    </>
  );
}
