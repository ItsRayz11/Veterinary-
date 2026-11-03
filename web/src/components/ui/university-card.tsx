import Image from "next/image";
import Link from "next/link";
import { ArrowRight, MapPin } from "lucide-react";
import type { UniversityBrief } from "@/lib/api";
import { Flag } from "./flag";
import { IconChip } from "./icons";
import { StatusBadge } from "./status-badge";

/** Openly licensed logo or photo when one is stored, otherwise the academic-building icon. */
export function UniversityImageBox({
  uni,
  sizes = "(min-width: 1024px) 30vw, (min-width: 640px) 45vw, 90vw",
  priority = false,
}: {
  uni: Pick<UniversityBrief, "name" | "image">;
  sizes?: string;
  priority?: boolean;
}) {
  if (!uni.image) {
    return (
      <span className="tone-blue flex h-full w-full items-center justify-center bg-[var(--tone-bg)]">
        <IconChip category="universities" size="lg" />
      </span>
    );
  }
  return (
    <Image
      src={uni.image.url}
      alt={`${uni.name}, image`}
      fill
      sizes={sizes}
      priority={priority}
      className="object-contain p-2"
    />
  );
}

export function UniversityCard({ uni }: { uni: UniversityBrief }) {
  return (
    <Link
      href={`/universities/${uni.slug}`}
      className="card card-link tone-blue prism-edge group flex h-full flex-col overflow-hidden"
    >
      <span className={`relative block bg-surface-2 ${uni.image ? "aspect-[16/9]" : "h-16"}`}>
        <UniversityImageBox uni={uni} />
      </span>
      <span className="flex flex-1 flex-col gap-2 p-4">
        <span className="font-medium leading-snug">{uni.name}</span>
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
          <span className="inline-flex items-center gap-1.5">
            <Flag iso2={uni.country} className="h-3.5 w-5" />
            {uni.country_name}
          </span>
          {uni.city && (
            <span className="inline-flex items-center gap-1">
              <MapPin size={13} aria-hidden="true" />
              {uni.city}
            </span>
          )}
        </span>
        <span className="mt-auto flex items-center justify-between pt-1">
          {uni.status.is_unverified_import ? <StatusBadge status="imported" /> : <span />}
          <ArrowRight
            size={16}
            aria-hidden="true"
            className="text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
          />
        </span>
      </span>
    </Link>
  );
}
