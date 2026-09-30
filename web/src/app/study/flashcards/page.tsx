import type { Metadata } from "next";
import { Flashcards } from "@/components/study/flashcards";
import { Breadcrumbs } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Flashcards", robots: { index: false } };

export default function FlashcardsPage() {
  return (
    <main className="space-y-4">
      <Breadcrumbs items={[{ label: "Study", href: "/study" }, { label: "Flashcards" }]} />
      <h1 className="text-xl font-semibold">Flashcards</h1>
      <Flashcards />
    </main>
  );
}
