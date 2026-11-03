import { PageTitle } from "@/components/ui/visual";
import type { Metadata } from "next";
import { Flashcards } from "@/components/study/flashcards";
import { Breadcrumbs } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Flashcards", robots: { index: false } };

export default function FlashcardsPage() {
  return (
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Study", href: "/study" }, { label: "Flashcards" }]} />
      <PageTitle category="mocktests">Flashcards</PageTitle>
      <Flashcards />
    </div>
  );
}
