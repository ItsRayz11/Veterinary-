import type { Metadata } from "next";
import { SubmitForm } from "@/components/listings/submit-form";

export const metadata: Metadata = { title: "Post a scholarship", robots: { index: false } };

export default function Page() {
  return <SubmitForm kind="scholarships" />;
}
