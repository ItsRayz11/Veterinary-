import type { Metadata } from "next";
import { ListingIndex } from "@/components/listings/listing-index";
import { apiGet } from "@/lib/api";
import type { Listing } from "@/lib/listings";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Scholarships",
  alternates: { canonical: "/scholarships" },
};

export default async function Page() {
  const items = await apiGet<Listing[]>("/listings/scholarships/", 30);
  return <ListingIndex kind="scholarships" items={items} />;
}
