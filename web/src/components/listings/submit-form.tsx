"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/primitives";
import { Button, Field, Select, TextInput } from "@/components/ui/forms";
import { ClientApiError, apiFetch, apiSend } from "@/lib/client-api";
import { FUNDING, JOB_TYPES, LABELS, LEVELS, type Kind } from "@/lib/listings";
import { useUser } from "@/lib/use-user";

interface Country {
  iso2: string;
  name: string;
}

export function SubmitForm({ kind }: { kind: Kind }) {
  const user = useUser();
  const [countries, setCountries] = useState<Country[]>([]);
  const [error, setError] = useState<ClientApiError | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const L = LABELS[kind];

  useEffect(() => {
    apiFetch<Country[]>("/countries")
      .then((c) => setCountries(c ?? []))
      .catch(() => {});
  }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const payload = Object.fromEntries(
      [...new FormData(e.currentTarget).entries()].filter(([, v]) => v !== ""),
    );
    setBusy(true);
    setError(null);
    try {
      await apiSend("POST", `/listings/${kind}/submit`, payload);
      setDone(true);
    } catch (err) {
      setError(
        err instanceof ClientApiError ? err : new ClientApiError("Something went wrong.", 0),
      );
    } finally {
      setBusy(false);
    }
  }

  if (user === null)
    return (
      <Alert tone="info">
        <Link className="underline" href={`/login?next=${L.newPath}`}>
          Sign in
        </Link>{" "}
        to post a {L.singular}.
      </Alert>
    );
  if (done)
    return (
      <Alert tone="ok" title="Submitted for review">
        A moderator will check it before it appears. Only the original posting link is shown to
        visitors.
      </Alert>
    );

  const fe = error?.fields ?? {};
  return (
    <form onSubmit={submit} className="mx-auto max-w-xl space-y-3" noValidate>
      <h1 className="text-xl font-semibold">Post a {L.singular}</h1>
      <p className="text-sm text-muted">
        Post only real opportunities you can link to. Listings are moderated and expire at the
        closing date (or after 90 days).
      </p>
      {error && !Object.keys(fe).length && <Alert tone="danger">{error.message}</Alert>}
      <Field id="title" label="Title" error={fe.title}>
        <TextInput id="title" name="title" required maxLength={200} error={fe.title} />
      </Field>
      <Field
        id="organization"
        label={kind === "jobs" ? "Employer" : "Provider"}
        error={fe.organization}
      >
        <TextInput
          id="organization"
          name="organization"
          required
          maxLength={200}
          error={fe.organization}
        />
      </Field>
      {kind === "jobs" ? (
        <>
          <Field id="job_type" label="Job type" error={fe.job_type}>
            <Select id="job_type" name="job_type" required defaultValue="" error={fe.job_type}>
              <option value="">Choose</option>
              {JOB_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="city" label="City (optional)">
            <TextInput id="city" name="city" maxLength={100} />
          </Field>
        </>
      ) : (
        <>
          <Field id="level" label="Level" error={fe.level}>
            <Select id="level" name="level" required defaultValue="" error={fe.level}>
              <option value="">Choose</option>
              {LEVELS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="funding" label="Funding" error={fe.funding}>
            <Select id="funding" name="funding" defaultValue="unknown" error={fe.funding}>
              {FUNDING.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
        </>
      )}
      <Field id="country" label="Country (optional)" error={fe.country}>
        <Select id="country" name="country" defaultValue="" error={fe.country}>
          <option value="">Not specified</option>
          {countries.map((c) => (
            <option key={c.iso2} value={c.iso2}>
              {c.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field id="description" label="Description" error={fe.description}>
        <textarea
          id="description"
          name="description"
          required
          maxLength={3000}
          rows={6}
          aria-invalid={!!fe.description}
          className="w-full rounded-md border border-border bg-surface p-3 text-sm"
        />
      </Field>
      <Field id="apply_url" label="Link to the original posting" error={fe.apply_url}>
        <TextInput id="apply_url" name="apply_url" type="url" required error={fe.apply_url} />
      </Field>
      <Field id="closes_on" label="Closing date (optional)" error={fe.closes_on}>
        <TextInput id="closes_on" name="closes_on" type="date" error={fe.closes_on} />
      </Field>
      <Button type="submit" loading={busy}>
        Submit for review
      </Button>
    </form>
  );
}
