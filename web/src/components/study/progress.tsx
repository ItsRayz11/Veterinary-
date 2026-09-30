"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";

interface Summary {
  history: { id: number; date: string; score: number; total: number; percent: number }[];
  subjects: { subject: string; correct: number; total: number; percent: number }[];
  weak_topics: {
    subject: string;
    topic: string;
    correct: number;
    total: number;
    percent: number;
  }[];
}

const W = 320;
const H = 100;

/** Exam scores over time plus accuracy per subject, from the user's submitted exams. */
export function Progress() {
  const [data, setData] = useState<Summary | null>(null);
  useEffect(() => {
    let live = true;
    apiFetch<Summary>("/study/progress")
      .then((d) => live && setData(d))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  if (!data || data.history.length === 0) return null;

  const pts = data.history.map((h, i) => {
    const x = data.history.length === 1 ? W / 2 : (i / (data.history.length - 1)) * (W - 20) + 10;
    const y = H - 10 - (h.percent / 100) * (H - 20);
    return { x, y, h };
  });
  return (
    <section aria-labelledby="prog-h" className="space-y-3">
      <h2 id="prog-h" className="font-semibold">
        Your progress
      </h2>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Exam scores over time: ${data.history.map((h) => `${h.percent}%`).join(", ")}`}
        className="w-full max-w-md text-primary"
      >
        <line x1="10" x2={W - 10} y1={H - 10} y2={H - 10} stroke="currentColor" opacity="0.2" />
        <line
          x1="10"
          x2={W - 10}
          y1={H - 10 - 0.6 * (H - 20)}
          y2={H - 10 - 0.6 * (H - 20)}
          stroke="currentColor"
          strokeDasharray="3 3"
          opacity="0.3"
        />
        <polyline
          points={pts.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
        {pts.map((p) => (
          <circle key={p.h.id} cx={p.x} cy={p.y} r="3" fill="currentColor" />
        ))}
      </svg>
      <p className="text-xs text-muted">
        Dashed line marks 60%. Latest: {data.history.at(-1)!.percent}%.
      </p>
      <ul className="space-y-1 text-sm">
        {data.subjects.map((s) => (
          <li key={s.subject}>
            {s.subject}: {s.percent}% ({s.correct}/{s.total})
          </li>
        ))}
      </ul>
      {data.weak_topics.length > 0 && (
        <p className="text-sm text-warn">
          Weak topics: {data.weak_topics.map((w) => `${w.topic} (${w.percent}%)`).join(", ")}
        </p>
      )}
    </section>
  );
}
