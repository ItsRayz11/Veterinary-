"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/primitives";
import { Button, Field, TextInput } from "@/components/ui/forms";
import { ClientApiError, apiFetch, apiSend } from "@/lib/client-api";
import { notifyAuthChanged } from "@/lib/use-user";

interface Status {
  enabled: boolean;
  required: boolean;
  verified: boolean;
  recovery_codes_left: number;
}

const message = (e: unknown) =>
  e instanceof ClientApiError
    ? (e.fields.code ?? e.fields.detail ?? e.message)
    : "Something went wrong.";

/** Two-factor authentication: turn on, recovery codes, turn off. */
export function SecuritySettings() {
  const [status, setStatus] = useState<Status | null>(null);
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    apiFetch<Status>("/auth/mfa/status")
      .then((s) => live && setStatus(s))
      .catch(() => live && setError("Could not load security settings."));
    return () => {
      live = false;
    };
  }, []);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  const start = () =>
    run(async () =>
      setSetup(await apiSend<{ secret: string; otpauth_uri: string }>("POST", "/auth/mfa/setup")),
    );

  const confirm = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const code = String(new FormData(e.currentTarget).get("code") ?? "");
    return run(async () => {
      const r = await apiSend<Status & { recovery_codes: string[] }>("POST", "/auth/mfa/confirm", {
        code,
      });
      setStatus(r);
      setCodes(r.recovery_codes);
      setSetup(null);
      notifyAuthChanged();
    });
  };

  const withCode =
    (path: string, after: (r: Status & { recovery_codes?: string[] }) => void) =>
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const code = String(new FormData(e.currentTarget).get("code") ?? "");
      return run(async () => {
        after(await apiSend<Status & { recovery_codes?: string[] }>("POST", path, { code }));
        notifyAuthChanged();
      });
    };

  if (!status) return error ? <Alert tone="danger">{error}</Alert> : null;

  return (
    <section
      aria-labelledby="mfa-h"
      className="space-y-3 rounded-md border border-border bg-surface p-4"
    >
      <h2 id="mfa-h" className="font-semibold">
        Two-factor authentication
      </h2>
      {error && <Alert tone="danger">{error}</Alert>}

      {codes && (
        <Alert tone="warn" title="Save your recovery codes now">
          <p>Each code works once if you lose your phone. They are not shown again.</p>
          <ul className="mt-2 grid grid-cols-2 gap-1 font-mono text-sm">
            {codes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <Button variant="secondary" className="mt-3" onClick={() => setCodes(null)}>
            I have saved them
          </Button>
        </Alert>
      )}

      {!status.enabled && !setup && (
        <>
          <p className="text-sm text-muted">
            {status.required
              ? "Required for staff accounts. "
              : "Adds a second step at sign-in using an authenticator app. "}
            Works with Google Authenticator, Authy, Microsoft Authenticator and 1Password.
          </p>
          <Button loading={busy} onClick={start}>
            Set up two-factor
          </Button>
        </>
      )}

      {setup && (
        <form onSubmit={confirm} className="space-y-3" noValidate>
          <p className="text-sm">
            In your authenticator app choose &ldquo;enter a setup key&rdquo; and type this key (or
            open the link on your phone), then enter the 6-digit code it shows.
          </p>
          <p className="break-all rounded bg-surface-2 p-2 font-mono text-sm">{setup.secret}</p>
          <p className="text-sm">
            <a className="text-primary underline" href={setup.otpauth_uri}>
              Open in authenticator app
            </a>
          </p>
          <Field id="mfa-code" label="6-digit code">
            <TextInput
              id="mfa-code"
              name="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
            />
          </Field>
          <Button type="submit" loading={busy}>
            Turn on two-factor
          </Button>
        </form>
      )}

      {status.enabled && !codes && (
        <div className="space-y-4">
          <p className="text-sm">
            <strong>On.</strong> {status.recovery_codes_left} recovery code
            {status.recovery_codes_left === 1 ? "" : "s"} left.
          </p>
          <form
            onSubmit={withCode("/auth/mfa/recovery", (r) => {
              setStatus(r);
              setCodes(r.recovery_codes ?? null);
            })}
            className="space-y-2"
            noValidate
          >
            <Field id="mfa-regen" label="New recovery codes (enter a current code to confirm)">
              <TextInput
                id="mfa-regen"
                name="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                required
              />
            </Field>
            <Button variant="secondary" type="submit" loading={busy}>
              Make new recovery codes
            </Button>
          </form>
          {!status.required && (
            <form
              onSubmit={withCode("/auth/mfa/disable", (r) => setStatus(r))}
              className="space-y-2"
              noValidate
            >
              <Field id="mfa-off" label="Turn off (enter a current code to confirm)">
                <TextInput
                  id="mfa-off"
                  name="code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                />
              </Field>
              <Button variant="danger" type="submit" loading={busy}>
                Turn off two-factor
              </Button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}
