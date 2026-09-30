"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Field, Select, Skeleton } from "@/components/ui/forms";
import { Alert, DataTable, EmptyState, td, th } from "@/components/ui/primitives";
import { ClientApiError, apiFetch, apiSend } from "@/lib/client-api";
import { useUser } from "@/lib/use-user";
import { Progress } from "./progress";
import type { ExamQuestion, HistoryRow, Subject } from "./types";

const SIZES = [20, 50, 100];
const DIFFICULTIES = ["easy", "medium", "hard"];

export function StudyHub() {
  const user = useUser();
  const router = useRouter();
  const [subjects, setSubjects] = useState<Subject[] | null>(null);
  const [subject, setSubject] = useState("");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [size, setSize] = useState(20);
  const [available, setAvailable] = useState<number | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch<Subject[]>("/study/subjects")
      .then((s) => setSubjects(s ?? []))
      .catch(() => setError("Could not load subjects."));
  }, []);

  const query = new URLSearchParams(
    Object.entries({ subject, topic, difficulty }).filter(([, v]) => v),
  ).toString();

  useEffect(() => {
    let live = true;
    apiFetch<ExamQuestion[]>(`/study/questions?${query}`)
      .then((q) => live && setAvailable(q?.length ?? 0))
      .catch(() => live && setAvailable(null));
    return () => {
      live = false;
    };
  }, [query]);

  useEffect(() => {
    if (!user) return;
    apiFetch<HistoryRow[]>("/study/exams/history")
      .then((h) => setHistory(h ?? []))
      .catch(() => {});
  }, [user]);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const body = { size, ...Object.fromEntries(new URLSearchParams(query)) };
      const exam = await apiSend<{ id: number }>("POST", "/study/exams", body);
      router.push(`/study/exams/${exam.id}`);
    } catch (e) {
      setError(
        e instanceof ClientApiError ? (e.fields.exam ?? e.message) : "Could not start the exam.",
      );
    } finally {
      setBusy(false);
    }
  }

  const topics = subjects?.find((s) => s.slug === subject)?.topics ?? [];

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Study</h1>
        <p className="text-sm text-muted">
          Timed-free mock exams built from reviewed questions. Answers stay hidden until you submit.
        </p>
      </header>

      {subjects === null && !error && <Skeleton className="h-32 w-full" />}
      {error && <Alert tone="danger">{error}</Alert>}

      {subjects && (
        <section
          aria-labelledby="exam-h"
          className="space-y-3 rounded-md border border-border bg-surface p-4"
        >
          <h2 id="exam-h" className="font-semibold">
            Start a mock exam
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="subject" label="Subject">
              <Select
                id="subject"
                value={subject}
                onChange={(e) => {
                  setSubject(e.target.value);
                  setTopic("");
                }}
              >
                <option value="">All subjects</option>
                {subjects.map((s) => (
                  <option key={s.slug} value={s.slug}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="topic" label="Topic">
              <Select
                id="topic"
                value={topic}
                disabled={!subject}
                onChange={(e) => setTopic(e.target.value)}
              >
                <option value="">All topics</option>
                {topics.map((t) => (
                  <option key={t.slug} value={t.slug}>
                    {t.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="difficulty" label="Difficulty">
              <Select
                id="difficulty"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
              >
                <option value="">Any</option>
                {DIFFICULTIES.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="size" label="Number of questions">
              <Select id="size" value={size} onChange={(e) => setSize(Number(e.target.value))}>
                {SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {available === 0 ? (
            <EmptyState title="No published questions match these filters.">
              Question content is added by reviewers. Nothing is invented, so an empty bank stays
              empty until real, sourced questions are published.
            </EmptyState>
          ) : (
            <p className="text-sm text-muted">
              {available === null
                ? "Checking availability…"
                : `${available >= 50 ? "50+" : available} matching questions available.`}
            </p>
          )}
          {user === null ? (
            <Alert tone="info">
              <Link href="/login?next=/study" className="underline">
                Sign in
              </Link>{" "}
              to take a mock exam and keep your results.
            </Alert>
          ) : (
            <Button onClick={start} loading={busy} disabled={!user || available === 0}>
              Start {size}-question exam
            </Button>
          )}
        </section>
      )}

      {user && <Progress />}

      {history.length > 0 && (
        <section aria-labelledby="hist-h" className="space-y-2">
          <h2 id="hist-h" className="font-semibold">
            Your previous exams
          </h2>
          <DataTable caption="Submitted exams">
            <thead>
              <tr>
                <th className={th}>Date</th>
                <th className={th}>Score</th>
                <th className={th}>Review</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id}>
                  <td className={td}>{new Date(h.date).toLocaleDateString()}</td>
                  <td className={td}>
                    {h.score}/{h.total} ({Math.round((100 * h.score) / h.total)}%)
                  </td>
                  <td className={td}>
                    <Link className="text-primary underline" href={`/study/exams/${h.id}`}>
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </section>
      )}

      <nav aria-label="Study tools" className="flex flex-wrap gap-4 text-sm">
        {[
          ["/study/flashcards", "Flashcards"],
          ["/study/lessons", "Lessons"],
          ["/study/books", "Book references"],
          ["/study/past-papers", "Past-paper index"],
        ].map(([href, label]) => (
          <Link key={href} className="text-primary underline" href={href}>
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
