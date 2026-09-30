"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Button, Field, Skeleton, TextInput } from "@/components/ui/forms";
import { Alert, DataTable, td, th } from "@/components/ui/primitives";
import { ClientApiError, apiFetch, apiSend } from "@/lib/client-api";
import { useUser } from "@/lib/use-user";
import type { ExamDetail, ExamQuestion } from "./types";

export function ExamRunner({ id }: { id: number }) {
  const user = useUser();
  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    if (!user) return;
    let live = true;
    apiFetch<ExamDetail>(`/study/exams/${id}`)
      .then((d) => {
        if (!live) return;
        if (d) setExam(d);
        else setError("Exam not found or you are not signed in.");
      })
      .catch(() => live && setError("Could not load this exam."));
    return () => {
      live = false;
    };
  }, [user, id, reloads]);

  if (user === undefined) return <Skeleton className="h-40 w-full" />;
  if (user === null)
    return (
      <Alert tone="info">
        <Link href={`/login?next=/study/exams/${id}`} className="underline">
          Sign in
        </Link>{" "}
        to open this exam.
      </Alert>
    );
  if (error) return <Alert tone="danger">{error}</Alert>;
  if (!exam) return <Skeleton className="h-40 w-full" />;
  return exam.submitted ? (
    <Results exam={exam} />
  ) : (
    <Runner exam={exam} onSubmitted={() => setReloads((n) => n + 1)} />
  );
}

function Runner({ exam, onSubmitted }: { exam: ExamDetail; onSubmitted: () => void }) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const q = exam.questions[index];
  const answered = Object.keys(answers).length;
  const total = exam.questions.length;

  async function submit() {
    const missing = total - answered;
    if (missing > 0 && !window.confirm(`${missing} question(s) are unanswered. Submit anyway?`))
      return;
    setBusy(true);
    setError(null);
    try {
      await apiSend("POST", `/study/exams/${exam.id}/submit`, { answers });
      onSubmitted();
    } catch (e) {
      setError(e instanceof ClientApiError ? (e.fields.exam ?? e.message) : "Submit failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex items-center justify-between text-sm text-muted">
        <span>
          Question {index + 1} of {total}
        </span>
        <span>{answered} answered</span>
      </div>
      <progress className="w-full" max={total} value={answered} aria-label="Answered questions" />
      {error && <Alert tone="danger">{error}</Alert>}
      <fieldset className="space-y-2">
        <legend className="mb-2 text-base font-medium">{q.stem}</legend>
        <p className="text-xs text-muted">
          {q.topic} · {q.difficulty}
        </p>
        {q.options.map((o) => (
          <label
            key={o.id}
            className="flex min-h-11 cursor-pointer items-start gap-2 rounded-md border border-border bg-surface p-3 has-[:checked]:border-primary"
          >
            <input
              type="radio"
              name={`q-${q.id}`}
              checked={answers[q.id] === o.id}
              onChange={() => setAnswers((a) => ({ ...a, [q.id]: o.id }))}
              className="mt-1"
            />
            <span>
              <span className="font-medium">{o.label}.</span> {o.text}
            </span>
          </label>
        ))}
      </fieldset>
      <div className="flex flex-wrap justify-between gap-2">
        <Button variant="secondary" disabled={index === 0} onClick={() => setIndex(index - 1)}>
          Previous
        </Button>
        {index < total - 1 ? (
          <Button onClick={() => setIndex(index + 1)}>Next</Button>
        ) : (
          <Button loading={busy} onClick={submit}>
            Submit exam
          </Button>
        )}
      </div>
      <nav aria-label="Question navigator" className="flex flex-wrap gap-1">
        {exam.questions.map((x, i) => (
          <button
            key={x.id}
            type="button"
            aria-label={`Question ${i + 1}${answers[x.id] ? ", answered" : ""}`}
            aria-current={i === index}
            onClick={() => setIndex(i)}
            className={`h-9 w-9 rounded border text-xs ${
              i === index ? "border-primary" : "border-border"
            } ${answers[x.id] ? "bg-primary text-primary-fg" : "bg-surface"}`}
          >
            {i + 1}
          </button>
        ))}
      </nav>
      {index !== total - 1 && (
        <Button variant="secondary" loading={busy} onClick={submit}>
          Submit exam
        </Button>
      )}
    </div>
  );
}

function Results({ exam }: { exam: ExamDetail }) {
  const total = exam.questions.length;
  const score = exam.score ?? 0;
  const topics = useMemo(() => {
    const m = new Map<string, [number, number]>();
    for (const q of exam.questions) {
      const t = m.get(q.topic) ?? [0, 0];
      t[1] += 1;
      t[0] += q.is_correct ? 1 : 0;
      m.set(q.topic, t);
    }
    return [...m.entries()]
      .map(([topic, [c, n]]) => ({ topic, c, n, pct: Math.round((100 * c) / n) }))
      .sort((a, b) => a.pct - b.pct);
  }, [exam.questions]);
  const weak = topics.filter((t) => t.pct < 60);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Results</h1>
        <p className="text-2xl font-semibold">
          {score}/{total}{" "}
          <span className="text-base text-muted">({Math.round((100 * score) / total)}%)</span>
        </p>
      </header>
      {weak.length > 0 && (
        <Alert tone="warn" title="Weak topics (under 60%)">
          {weak.map((t) => t.topic).join(", ")}
        </Alert>
      )}
      <DataTable caption="Score by topic">
        <thead>
          <tr>
            <th className={th}>Topic</th>
            <th className={th}>Correct</th>
            <th className={th}>Percent</th>
          </tr>
        </thead>
        <tbody>
          {topics.map((t) => (
            <tr key={t.topic}>
              <td className={td}>{t.topic}</td>
              <td className={td}>
                {t.c}/{t.n}
              </td>
              <td className={td}>{t.pct}%</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <section aria-labelledby="review-h" className="space-y-3">
        <h2 id="review-h" className="font-semibold">
          Review
        </h2>
        {exam.questions.map((q, i) => (
          <ReviewCard key={q.id} q={q} n={i + 1} />
        ))}
      </section>
      <Link href="/study" className="text-primary underline">
        Back to study hub
      </Link>
    </div>
  );
}

function ReviewCard({ q, n }: { q: ExamQuestion; n: number }) {
  const [bookmarked, setBookmarked] = useState<boolean | null>(null);
  const [reporting, setReporting] = useState(false);
  const [message, setMessage] = useState("");
  const [note, setNote] = useState<string | null>(null);

  async function toggle() {
    try {
      const r = await apiSend<{ bookmarked: boolean }>("POST", `/study/questions/${q.id}/bookmark`);
      setBookmarked(r.bookmarked);
    } catch {
      setNote("Could not update bookmark.");
    }
  }
  async function report() {
    try {
      await apiSend("POST", `/study/questions/${q.id}/report`, { message });
      setReporting(false);
      setMessage("");
      setNote("Thanks, the report was sent to the editors.");
    } catch (e) {
      setNote(e instanceof ClientApiError ? (e.fields.message ?? e.message) : "Could not send.");
    }
  }

  return (
    <article className="space-y-2 rounded-md border border-border bg-surface p-3 text-sm">
      <p className="font-medium">
        {n}. {q.stem}{" "}
        <span className={q.is_correct ? "text-ok" : "text-danger"}>
          ({q.is_correct ? "correct" : q.selected ? "incorrect" : "unanswered"})
        </span>
      </p>
      <ul className="space-y-1">
        {q.options.map((o) => {
          const right = o.id === q.correct_option;
          const chosen = o.id === q.selected;
          return (
            <li
              key={o.id}
              className={`rounded px-2 py-1 ${right ? "bg-ok-bg text-ok" : chosen ? "bg-danger-bg text-danger" : ""}`}
            >
              {o.label}. {o.text}
              {right && " ✓ correct answer"}
              {chosen && !right && " ✗ your answer"}
            </li>
          );
        })}
      </ul>
      {q.explanation && <p className="text-muted">{q.explanation}</p>}
      <div className="flex flex-wrap gap-3">
        <button type="button" className="text-primary underline" onClick={toggle}>
          {bookmarked ? "Remove bookmark" : "Bookmark"}
        </button>
        <button
          type="button"
          className="text-primary underline"
          onClick={() => setReporting(!reporting)}
        >
          Report a problem
        </button>
      </div>
      {reporting && (
        <div className="space-y-2">
          <Field id={`rep-${q.id}`} label="What is wrong with this question?">
            <TextInput
              id={`rep-${q.id}`}
              value={message}
              maxLength={500}
              onChange={(e) => setMessage(e.target.value)}
            />
          </Field>
          <Button disabled={!message.trim()} onClick={report}>
            Send report
          </Button>
        </div>
      )}
      {note && (
        <p role="status" className="text-xs text-muted">
          {note}
        </p>
      )}
    </article>
  );
}
