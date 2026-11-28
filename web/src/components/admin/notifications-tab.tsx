"use client";

import { useCallback, useEffect, useState } from "react";
import { NotificationSettings } from "@/components/notification-settings";
import { Button, Skeleton } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { apiFetch, apiSend } from "@/lib/client-api";
import { errText } from "./tabs";

interface Status {
  server_enabled: boolean;
  devices: number;
  digest_schedule: string;
  delivered?: number;
}

/**
 * Staff notifications: turn push on for this device, send yourself a test, and (admins) send the
 * daily digest now. The digest lists the same items as the dashboard's "Needs attention".
 */
export function NotificationsTab({ isAdmin }: { isAdmin: boolean }) {
  const [status, setStatus] = useState<Status | null | undefined>(undefined);
  const [note, setNote] = useState<{ tone: "ok" | "warn" | "danger"; text: string } | null>(null);
  const [busy, setBusy] = useState<"test" | "digest" | null>(null);

  const load = useCallback(() => {
    apiFetch<Status>("/staff/notifications")
      .then((s) => setStatus(s ?? null))
      .catch(() => setStatus(null));
  }, []);
  useEffect(load, [load]);

  async function sendTest() {
    setBusy("test");
    setNote(null);
    try {
      const out = await apiSend<Status>("POST", "/staff/notifications");
      setStatus(out);
      setNote(
        out.delivered
          ? { tone: "ok", text: `Sent to ${out.delivered} device(s). It should appear shortly.` }
          : {
              tone: "warn",
              text: "Nothing was delivered. Turn notifications on for this device first.",
            },
      );
    } catch (e) {
      setNote({ tone: "danger", text: errText(e) });
    } finally {
      setBusy(null);
    }
  }

  async function sendDigest() {
    setBusy("digest");
    setNote(null);
    try {
      const run = await apiSend<{
        status: string;
        error?: string;
        summary?: { items?: number; notified_devices?: number };
      }>("POST", "/staff/automation/run/staff-digest");
      if (run?.status !== "ok") {
        setNote({ tone: "danger", text: `The digest run failed: ${run?.error || "no detail"}` });
        return;
      }
      const items = run.summary?.items ?? 0;
      const devices = run.summary?.notified_devices ?? 0;
      setNote(
        !items
          ? { tone: "ok", text: "Nothing needs attention, so no notification was sent." }
          : devices
            ? { tone: "ok", text: `${items} item(s) need attention; sent to ${devices} device(s).` }
            : {
                tone: "warn",
                text: `${items} item(s) on the dashboard, but no notification went out (only informational items, or no staff device has notifications on).`,
              },
      );
    } catch (e) {
      setNote({ tone: "danger", text: errText(e) });
    } finally {
      setBusy(null);
    }
  }

  if (status === undefined) return <Skeleton className="h-32 w-full" />;
  if (status === null) return <Alert tone="danger">Could not load notification settings.</Alert>;

  return (
    <div className="space-y-4">
      {!status.server_enabled && (
        <Alert tone="warn" title="Notifications are not switched on for the site yet">
          <p>The API needs a key pair for web push. One-time setup:</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            <li>
              On a trusted computer, in the <code>api</code> folder, run{" "}
              <code>python manage.py generate_vapid_keys</code>.
            </li>
            <li>
              In Vercel, open the API project, Settings, Environment Variables. Add{" "}
              <code>VAPID_PUBLIC_KEY</code> and <code>VAPID_PRIVATE_KEY</code> from the output, and{" "}
              <code>VAPID_SUBJECT</code> as <code>mailto:</code> plus your address.
            </li>
            <li>Redeploy the API, then come back here and turn notifications on.</li>
          </ol>
          <p className="mt-2">Keep the private key out of chat, email and git.</p>
        </Alert>
      )}

      <NotificationSettings
        showUnavailable
        onChange={load}
        description="Get the daily digest on this device: failed or missed scheduled jobs, held imports, broken sources, unusual prices and new errors. Turn it on separately on each phone or computer you use."
      />

      <section aria-labelledby="notify-status-h" className="card space-y-3 p-4 text-sm">
        <h2 id="notify-status-h" className="text-base font-semibold">
          Delivery
        </h2>
        <dl className="grid gap-2 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-muted">Your devices receiving notifications</dt>
            <dd className="text-lg font-medium">{status.devices}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Daily digest</dt>
            <dd>{status.digest_schedule}</dd>
          </div>
        </dl>
        {note && <Alert tone={note.tone === "ok" ? "ok" : note.tone}>{note.text}</Alert>}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            loading={busy === "test"}
            disabled={!status.server_enabled || busy !== null}
            onClick={sendTest}
          >
            Send me a test notification
          </Button>
          {isAdmin && (
            <Button
              variant="secondary"
              loading={busy === "digest"}
              disabled={busy !== null}
              onClick={sendDigest}
            >
              Send today&apos;s digest now
            </Button>
          )}
        </div>
      </section>
    </div>
  );
}
