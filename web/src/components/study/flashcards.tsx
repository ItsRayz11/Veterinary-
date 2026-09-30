"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, Skeleton } from "@/components/ui/forms";
import { Alert, EmptyState } from "@/components/ui/primitives";
import { apiFetch, apiSend } from "@/lib/client-api";
import { useUser } from "@/lib/use-user";

interface Card {
  id: number;
  front: string;
  back: string;
  topic: string;
  subject: string;
}

/** Spaced-repetition session (Leitner boxes are scheduled on the server). */
export function Flashcards() {
  const user = useUser();
  const [cards, setCards] = useState<Card[] | null>(null);
  const [i, setI] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewed, setReviewed] = useState(0);

  useEffect(() => {
    if (!user) return;
    let live = true;
    apiFetch<Card[]>("/study/flashcards/due")
      .then((c) => live && setCards(c ?? []))
      .catch(() => live && setError("Could not load flashcards."));
    return () => {
      live = false;
    };
  }, [user]);

  if (user === undefined) return <Skeleton className="h-40 w-full" />;
  if (user === null)
    return (
      <Alert tone="info">
        <Link href="/login?next=/study/flashcards" className="underline">
          Sign in
        </Link>{" "}
        to study flashcards; your progress is saved per account.
      </Alert>
    );
  if (error) return <Alert tone="danger">{error}</Alert>;
  if (!cards) return <Skeleton className="h-40 w-full" />;
  if (cards.length === 0)
    return (
      <EmptyState title="No cards to review right now.">
        Either every card is scheduled for later, or no reviewed flashcards are published yet.
        Flashcards appear only after they are sourced and reviewed.
      </EmptyState>
    );
  if (i >= cards.length)
    return (
      <div className="space-y-2">
        <Alert tone="ok" title="Session complete">
          You reviewed {reviewed} card(s). Come back when more are due.
        </Alert>
        <Link href="/study" className="text-primary underline">
          Back to study hub
        </Link>
      </div>
    );

  const card = cards[i];
  async function answer(correct: boolean) {
    try {
      await apiSend("POST", `/study/flashcards/${card.id}/review`, { correct });
      setReviewed((n) => n + 1);
      setFlipped(false);
      setI((n) => n + 1);
    } catch {
      setError("Could not save your answer. Try again.");
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <p className="text-sm text-muted">
        Card {i + 1} of {cards.length} · {card.topic}
      </p>
      <div
        className="min-h-40 rounded-md border border-border bg-surface p-5 text-lg"
        aria-live="polite"
      >
        {flipped ? card.back : card.front}
      </div>
      {flipped ? (
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => answer(false)}>
            I got it wrong
          </Button>
          <Button onClick={() => answer(true)}>I got it right</Button>
        </div>
      ) : (
        <Button onClick={() => setFlipped(true)}>Show answer</Button>
      )}
    </div>
  );
}
