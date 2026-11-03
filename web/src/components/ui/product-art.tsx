import type { ReactNode } from "react";

type Kind = "tablet" | "injectable" | "liquid" | "topical" | "generic";

/** Picks a generic artwork type from pack form text. Never implies a specific product or its packaging. */
export function artKind(forms: string[]): Kind {
  const f = forms.join(" ").toLowerCase();
  if (/(inject|vial|ampoul|intravenous|subcutaneous|intramuscular)/.test(f)) return "injectable";
  if (/(tablet|capsule|bolus|chew|pill)/.test(f)) return "tablet";
  if (/(oral|solution|suspension|syrup|drench|liquid|drops|water)/.test(f)) return "liquid";
  if (/(spot|pour|cream|ointment|gel|spray|powder|topical|shampoo)/.test(f)) return "topical";
  return "generic";
}

const ART: Record<Kind, ReactNode> = {
  tablet: (
    <>
      <rect x="14" y="16" width="36" height="16" rx="8" transform="rotate(-30 32 24)" />
      <path d="M26.5 14.4l11 19" />
    </>
  ),
  injectable: (
    <>
      <path d="M26 4h12M28 4v6h8V4M24 10h16v8l-2 3v21a3 3 0 0 1-3 3H29a3 3 0 0 1-3-3V21l-2-3z" />
      <path d="M26 30h12" />
    </>
  ),
  liquid: (
    <>
      <path d="M26 4h12v6H26zM24 10h16l2 6v26a3 3 0 0 1-3 3H25a3 3 0 0 1-3-3V16z" />
      <path d="M22 28h20" />
    </>
  ),
  topical: (
    <>
      <path d="M22 6h20v8H22zM20 14h24l-3 30a2 2 0 0 1-2 2H25a2 2 0 0 1-2-2z" />
      <path d="M26 24h12" />
    </>
  ),
  generic: (
    <>
      <rect x="18" y="8" width="28" height="34" rx="5" />
      <path d="M32 18v14M25 25h14" />
    </>
  ),
};

/** Category-level placeholder shown until a verified product image exists. Decorative. */
export function ProductArt({ forms }: { forms: string[] }) {
  return (
    <span aria-hidden="true" className="icon-chip tone-teal h-20 w-20 shrink-0 rounded-xl">
      <svg
        viewBox="0 0 64 48"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-12 w-14"
      >
        {ART[artKind(forms)]}
      </svg>
    </span>
  );
}
