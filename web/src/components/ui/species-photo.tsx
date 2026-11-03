import Image from "next/image";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import credits from "@/lib/image-credits.json";
import { IconChip, speciesIcon } from "./icons";

interface Credit {
  file: string;
  page: string;
  credit: string;
  license: string;
  license_url: string;
}

const SPECIES = (credits as { species: Record<string, Credit> }).species;

/** Credit for a species photo, or undefined when none is stored. */
export function speciesCredit(slug: string): Credit | undefined {
  return SPECIES[slug];
}

/**
 * Real, openly licensed photograph of a species (see /credits), cropped to a fixed ratio.
 * Without one, a species icon is shown, so a species is never paired with the wrong animal.
 */
export function SpeciesPhoto({
  slug,
  name,
  sizes = "(min-width: 768px) 25vw, 50vw",
  priority = false,
  className = "aspect-[4/3]",
}: {
  slug: string;
  name: string;
  sizes?: string;
  priority?: boolean;
  className?: string;
}) {
  const c = SPECIES[slug];
  if (!c) {
    return (
      <span
        className={`flex items-center justify-center bg-[var(--tone-bg)] tone-green ${className}`}
      >
        <IconChip icon={speciesIcon(`${slug} ${name}`)} category="species" size="lg" />
      </span>
    );
  }
  return (
    <span className={`relative block overflow-hidden bg-surface-2 ${className}`}>
      <Image
        src={c.file}
        alt={name}
        fill
        sizes={sizes}
        priority={priority}
        className="object-cover"
      />
    </span>
  );
}

/** Photo-led link card for a species: image on top, name and arrow below. */
export function SpeciesCard({
  slug,
  name,
  priority = false,
}: {
  slug: string;
  name: string;
  priority?: boolean;
}) {
  return (
    <Link href={`/species/${slug}`} className="card card-link group block overflow-hidden">
      <SpeciesPhoto slug={slug} name={name} priority={priority} />
      <span className="flex items-center justify-between gap-2 p-3 font-medium">
        {name}
        <ArrowRight
          size={16}
          aria-hidden="true"
          className="text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
        />
      </span>
    </Link>
  );
}
