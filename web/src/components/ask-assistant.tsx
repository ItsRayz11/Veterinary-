"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Alert, EmptyState } from "@/components/ui/primitives";
import { Button, Field, Skeleton, TextInput } from "@/components/ui/forms";
import { ClientApiError, apiSend } from "@/lib/client-api";
import { useUser } from "@/lib/use-user";

interface Answer {
  status:
    "answered" | "no_reviewed_data" | "unverified" | "unavailable" | "error" | "too_many_drugs";
  answer: string;
  citations: string[];
  sources: { tag: string; name: string; slug: string }[];
  detail: string;
  disclaimer: string;
}

export function AskAssistant() {
  const user = useUser();
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await apiSend<Answer>("POST", "/assistant/ask", { question }));
    } catch (err) {
      setError(
        err instanceof ClientApiError
          ? (err.fields.question ?? err.message)
          : "Something went wrong.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (user === undefined) return <Skeleton className="h-24 w-full" />;
  if (user === null)
    return (
      <Alert tone="info">
        <Link href="/login?next=/ask" className="underline">
          Sign in
        </Link>{" "}
        to ask questions about reviewed drug records.
      </Alert>
    );

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="space-y-3" noValidate>
        <Field
          id="q"
          label="Your question"
          hint="Name the drug, e.g. “What does the record say about enrofloxacin in cattle?”"
        >
          <TextInput
            id="q"
            value={question}
            maxLength={500}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </Field>
        <Button type="submit" loading={busy} disabled={question.trim().length < 5}>
          Ask
        </Button>
      </form>
      {error && <Alert tone="danger">{error}</Alert>}
      <div aria-live="polite" className="space-y-3">
        {result?.status === "answered" && (
          <div className="space-y-2 rounded-md border border-border bg-surface p-4">
            <p className="whitespace-pre-line">{result.answer}</p>
            <p className="text-xs text-muted">
              Based on:{" "}
              {result.sources.map((s) => (
                <Link key={s.tag} className="text-primary underline" href={`/drugs/${s.slug}`}>
                  {s.name} [{s.tag}]{" "}
                </Link>
              ))}
            </p>
          </div>
        )}
        {result?.status === "no_reviewed_data" && (
          <EmptyState title="No reviewed record matches this question.">
            The assistant only answers about drugs that have reviewed records. Try the generic name
            of the drug, or use search.
          </EmptyState>
        )}
        {result?.status === "unverified" && (
          <Alert tone="warn" title="The answer could not be verified">
            The generated answer did not pass the checks (it must cite the records and use only
            numbers found in them), so it is not shown. Read the records directly:
          </Alert>
        )}
        {result?.status === "too_many_drugs" && (
          <Alert tone="warn" title="Please ask about fewer drugs">
            {result.detail} Answering from only some of them could look complete when it is not.
          </Alert>
        )}
        {result?.status === "unavailable" && (
          <Alert tone="info" title="The assistant is not switched on">
            These reviewed records match your question:
          </Alert>
        )}
        {result?.status === "error" && (
          <Alert tone="danger" title="The assistant could not answer">
            {result.detail || "Please try again later."}
          </Alert>
        )}
        {result && result.status !== "answered" && result.sources.length > 0 && (
          <ul className="space-y-1 text-sm">
            {result.sources.map((s) => (
              <li key={s.tag}>
                <Link className="text-primary underline" href={`/drugs/${s.slug}`}>
                  {s.name}
                </Link>
              </li>
            ))}
          </ul>
        )}
        {result && <p className="text-xs text-muted">{result.disclaimer}</p>}
      </div>
    </div>
  );
}
