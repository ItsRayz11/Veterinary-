import type { Metadata } from "next";
import { StudyHub } from "@/components/study/study-hub";

export const metadata: Metadata = { title: "Study" };

export default function StudyPage() {
  return <StudyHub />;
}
