"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Button, Field, TextInput } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { ClientApiError, apiSend } from "@/lib/client-api";
import { useUser } from "@/lib/use-user";

export function ArticleSubmitForm() {
  const user = useUser();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  if (user === undefined) return null;
  if (!user)
    return (
      <Alert tone="info">
        <Link href="/login?next=/blog/submit" className="underline">
          Sign in
        </Link>{" "}
        to submit an article.
      </Alert>
    );
  if (done)
    return (
      <Alert tone="info" title="Thank you">
        Your article was sent to the editors. It will appear once approved. Articles that mention
        dosing or treatment also need a veterinarian reviewer and cited references.
      </Alert>
    );

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await apiSend("POST", "/articles/submit/", Object.fromEntries(f.entries()));
      setDone(true);
    } catch (err) {
      setError(err instanceof ClientApiError ? err.message : "Could not send the article.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-sm text-muted">
        Plain text. Use # for headings, - for lists and [text](https://link) for links. HTML is
        removed. An editor reviews every article before it is public.
      </p>
      {error && <Alert tone="danger">{error}</Alert>}
      <Field id="title" label="Title">
        <TextInput id="title" name="title" required maxLength={200} />
      </Field>
      <Field id="excerpt" label="Short summary" hint="Up to 300 characters">
        <TextInput id="excerpt" name="excerpt" maxLength={300} />
      </Field>
      <Field id="category" label="Category">
        <TextInput id="category" name="category" maxLength={60} />
      </Field>
      <Field id="tags" label="Tags" hint="Comma separated">
        <TextInput id="tags" name="tags" maxLength={200} />
      </Field>
      <Field id="body" label="Article">
        <textarea
          id="body"
          name="body"
          required
          minLength={200}
          rows={14}
          className="neo-inset w-full rounded-lg border border-border px-3 py-2 text-sm"
        />
      </Field>
      <Field id="references" label="References" hint="One https link per line">
        <textarea
          id="references"
          name="references"
          rows={3}
          className="neo-inset w-full rounded-lg border border-border px-3 py-2 text-sm"
        />
      </Field>
      <Button type="submit" loading={busy}>
        Send for review
      </Button>
    </form>
  );
}
