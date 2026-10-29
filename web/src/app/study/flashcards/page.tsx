import type { Metadata } from "next";
import { Flashcards } from "@/components/study/flashcards";
import { Breadcrumbs } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Flashcards", robots: { index: false } };

export default function FlashcardsPage() {
  return (
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Study", href: "/study" }, { label: "Flashcards" }]} />
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Flashcards</h1>
      <Flashcards />
    </div>
  );
}
