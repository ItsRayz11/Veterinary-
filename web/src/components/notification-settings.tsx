"use client";

import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/primitives";
import { Button } from "@/components/ui/forms";
import { apiFetch, apiSend } from "@/lib/client-api";
import { keyToBytes, pushSupported } from "@/lib/push";

type State = "loading" | "unsupported" | "off-server" | "blocked" | "off" | "on";

/** Opt in to a notice when a job or scholarship you posted is approved or declined. */
export function NotificationSettings() {
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
    } catch {
      setError("Could not turn notifications off. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (state === "loading" || state === "unsupported" || state === "off-server") return null;

  return (
    <section
      aria-labelledby="notify-heading"
      className="space-y-2 rounded-md border border-border p-4"
    >
      <h2 id="notify-heading" className="text-lg font-semibold">
        Notifications
      </h2>
      <p className="text-sm text-muted">
        Get a notice on this device when a job or scholarship you posted is approved or declined.
        Nothing else is sent, and you can turn it off at any time.
      </p>
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
