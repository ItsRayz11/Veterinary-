import type { Metadata } from "next";
import { SubmitForm } from "@/components/listings/submit-form";

export const metadata: Metadata = { title: "Post a job", robots: { index: false } };

export default function Page() {
  return <SubmitForm kind="jobs" />;
}
