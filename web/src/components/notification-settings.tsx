"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Alert } from "@/components/ui/primitives";
import { Button } from "@/components/ui/forms";
import { apiFetch, apiSend } from "@/lib/client-api";
import { keyToBytes, pushSupported } from "@/lib/push";

type State = "loading" | "unsupported" | "off-server" | "blocked" | "off" | "on";

const DEFAULT_DESCRIPTION =
  "Get a notice on this device when a job or scholarship you posted is approved or declined. Nothing else is sent, and you can turn it off at any time.";

/**
 * Opt this device in or out of web push. The Account page uses the default wording; the review
 * panel passes its own (staff also get the daily digest) and asks to see why it is unavailable.
 */
export function NotificationSettings({
  description = DEFAULT_DESCRIPTION,
  onChange,
  showUnavailable = false,
}: {
  description?: ReactNode;
  /** Called after this device is turned on or off. */
  onChange?: () => void;
  /** Explain an unsupported browser or a server without push instead of rendering nothing. */
  showUnavailable?: boolean;
} = {}) {
  const [state, setState] = useState<State>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    (async () => {
      if (!pushSupported()) return live && setState("unsupported");
      const cfg = await apiFetch<{ enabled: boolean }>("/push/config");
      if (!cfg?.enabled) return live && setState("off-server");
      if (Notification.permission === "denied") return live && setState("blocked");
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (live) setState(sub ? "on" : "off");
    })().catch(() => live && setState("unsupported"));
    return () => {
      live = false;
    };
  }, []);

  async function enable() {
    setBusy(true);
    setError(null);
    try {
      const cfg = await apiFetch<{ public_key: string }>("/push/config");
      if (!cfg?.public_key) throw new Error("not enabled");
      if ((await Notification.requestPermission()) !== "granted") {
        setState("blocked");
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyToBytes(cfg.public_key),
      });
      await apiSend("POST", "/push/subscribe", sub.toJSON());
      setState("on");
      onChange?.();
    } catch {
      setError("Could not turn notifications on. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setBusy(true);
    setError(null);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await apiSend("POST", "/push/unsubscribe", { endpoint: sub.endpoint });
        await sub.unsubscribe();
      }
      setState("off");
      onChange?.();
    } catch {
      setError("Could not turn notifications off. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (state === "loading") return null;
  if (state === "unsupported" || state === "off-server") {
    if (!showUnavailable) return null;
    return (
      <p className="text-sm text-muted">
        {state === "unsupported"
          ? "This browser cannot receive notifications. On iPhone and iPad, add the site to the Home Screen first, then open it from there."
          : "Notifications are not switched on for the site yet (see above)."}
      </p>
    );
  }

  return (
    <section aria-labelledby="notify-heading" className="space-y-2 card p-4">
      <h2 id="notify-heading" className="text-lg font-semibold">
        Notifications
      </h2>
      <p className="text-sm text-muted">{description}</p>
      {error && <Alert tone="danger">{error}</Alert>}
      {state === "blocked" && (
        <p className="text-sm">
          Notifications are blocked for this site. Allow them in your browser settings to turn this
          on.
        </p>
      )}
      {state === "off" && (
        <Button onClick={enable} disabled={busy}>
          Turn on notifications
        </Button>
      )}
      {state === "on" && (
        <Button variant="secondary" onClick={disable} disabled={busy}>
          Turn off notifications
        </Button>
      )}
    </section>
  );
}
