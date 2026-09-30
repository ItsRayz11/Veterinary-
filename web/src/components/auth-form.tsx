"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/primitives";
import { Button, Field, Select, TextInput } from "@/components/ui/forms";
import { ClientApiError, apiSend } from "@/lib/client-api";
import { safeNext } from "@/lib/safe-next";
import { notifyAuthChanged } from "@/lib/use-user";

const ROLES = [
  { value: "registered", label: "General user" },
  { value: "student", label: "Veterinary student" },
  { value: "professional", label: "Veterinary professional" },
];

/** Roles chosen here are self-declared; privileged roles are only granted by admins. */
export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [error, setError] = useState<ClientApiError | null>(null);
  const [busy, setBusy] = useState(false);
  // After a correct password, accounts with two-factor on must also enter a code.
  const [needsCode, setNeedsCode] = useState(false);
  const register = mode === "register";

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const payload = Object.fromEntries(
      [...f.entries()].filter(([, v]) => typeof v === "string" && v !== ""),
    );
    setBusy(true);
    setError(null);
    try {
      if (needsCode) {
        await apiSend("POST", "/auth/mfa/verify", { code: payload.code });
      } else {
        const res = await apiSend<{ mfa_required?: boolean }>(
          "POST",
          register ? "/auth/register" : "/auth/login",
          payload,
        );
        if (res?.mfa_required) {
          setNeedsCode(true);
          return;
        }
      }
      notifyAuthChanged();
      router.push(
        safeNext(new URLSearchParams(window.location.search).get("next"), window.location.origin),
      );
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ClientApiError ? err : new ClientApiError("Something went wrong.", 0),
      );
    } finally {
      setBusy(false);
    }
  }

  const fe = error?.fields ?? {};
  const fieldKeys = Object.keys(fe).filter((k) => k !== "non_field_errors" && k !== "detail");

  if (needsCode) {
    return (
      <form onSubmit={submit} className="mx-auto max-w-sm space-y-4" noValidate>
        <h1 className="text-xl font-semibold">Two-factor code</h1>
        <p className="text-sm text-muted">
          Enter the 6-digit code from your authenticator app, or one of your recovery codes.
        </p>
        {error && <Alert tone="danger">{fe.code ?? fe.detail ?? error.message}</Alert>}
        <Field id="code" label="Code">
          <TextInput
            id="code"
            name="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            autoFocus
            required
          />
        </Field>
        <Button type="submit" loading={busy} className="w-full">
          Verify
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-sm space-y-4" noValidate>
      <h1 className="text-xl font-semibold">{register ? "Create an account" : "Sign in"}</h1>
      {error && fieldKeys.length === 0 && <Alert tone="danger">{error.message}</Alert>}
      <Field id="username" label="Username" error={fe.username}>
        <TextInput
          id="username"
          name="username"
          autoComplete="username"
          required
          error={fe.username}
        />
      </Field>
      {register && (
        <Field id="email" label="Email" error={fe.email}>
          <TextInput
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            error={fe.email}
          />
        </Field>
      )}
      <Field
        id="password"
        label="Password"
        error={fe.password}
        hint={register ? "At least 8 characters; not a common password." : undefined}
      >
        <TextInput
          id="password"
          name="password"
          type="password"
          autoComplete={register ? "new-password" : "current-password"}
          required
          error={fe.password}
          hint={register ? "At least 8 characters; not a common password." : undefined}
        />
      </Field>
      {register && (
        <Field
          id="role"
          label="I am a"
          error={fe.role}
          hint="Self-declared. Reviewer and admin access is granted separately."
        >
          <Select id="role" name="role" defaultValue="registered" error={fe.role}>
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
        </Field>
      )}
      <Button type="submit" loading={busy} className="w-full">
        {register ? "Create account" : "Sign in"}
      </Button>
      <p className="text-sm text-muted">
        {register ? "Already registered? " : "No account? "}
        <Link className="text-primary underline" href={register ? "/login" : "/register"}>
          {register ? "Sign in" : "Register"}
        </Link>
      </p>
    </form>
  );
}
