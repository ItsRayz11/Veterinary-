import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ExamRunner } from "@/components/study/exam-runner";

export const metadata: Metadata = { title: "Mock exam", robots: { index: false } };

export default async function ExamPage({ params }: PageProps<"/study/exams/[id]">) {
  const { id } = await params;
  const n = Number(id);
  if (!Number.isInteger(n) || n <= 0) notFound();
  return <ExamRunner id={n} />;
}
