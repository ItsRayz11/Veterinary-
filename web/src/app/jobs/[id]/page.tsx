import type { Metadata } from "next";
import { ListingDetail } from "@/components/listings/listing-detail";
import { apiGet } from "@/lib/api";
import type { Listing } from "@/lib/listings";

export async function generateMetadata({ params }: PageProps<"/jobs/[id]">): Promise<Metadata> {
  const { id } = await params;
  const item = await apiGet<Listing>(`/listings/jobs/${id}/`, 30);
  return { title: item.title, alternates: { canonical: `/jobs/${item.id}` } };
}

export default async function Page({ params }: PageProps<"/jobs/[id]">) {
  const { id } = await params;
  const item = await apiGet<Listing>(`/listings/jobs/${id}/`, 30);
  return <ListingDetail kind="jobs" item={item} />;
}
