import type { Metadata } from "next";
import { ListingIndex } from "@/components/listings/listing-index";
import { apiGet } from "@/lib/api";
import type { Listing } from "@/lib/listings";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Jobs",
  alternates: { canonical: "/jobs" },
};

export default async function Page() {
  const items = await apiGet<Listing[]>("/listings/jobs/", 30);
  return <ListingIndex kind="jobs" items={items} />;
}
