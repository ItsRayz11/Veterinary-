import type { Metadata } from "next";
import { ListingDetail } from "@/components/listings/listing-detail";
import { apiGet } from "@/lib/api";
import type { Listing } from "@/lib/listings";

export async function generateMetadata({
  params,
}: PageProps<"/scholarships/[id]">): Promise<Metadata> {
  const { id } = await params;
  const item = await apiGet<Listing>(`/listings/scholarships/${id}/`, 30);
  return { title: item.title, alternates: { canonical: `/scholarships/${item.id}` } };
}

export default async function Page({ params }: PageProps<"/scholarships/[id]">) {
  const { id } = await params;
  const item = await apiGet<Listing>(`/listings/scholarships/${id}/`, 30);
  return <ListingDetail kind="scholarships" item={item} />;
}
