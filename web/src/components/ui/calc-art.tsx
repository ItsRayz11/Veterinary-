import type { ReactNode } from "react";
import type { Tone } from "./icons";

/** Small line illustrations (64x48) drawn for each calculator. Decorative; the title carries the meaning. */
const ART: Record<string, ReactNode> = {
  "dose-calculator": (
    <>
      <rect x="14" y="16" width="36" height="16" rx="8" transform="rotate(-30 32 24)" />
      <path d="M26.5 14.4l11 19" />
      <path d="M8 42h10M12 38v8" />
    </>
  ),
  dilution: (
    <>
      <path d="M24 6h16M26 6v12L16 38a4 4 0 0 0 3.5 6h25a4 4 0 0 0 3.5-6L38 18V6" />
      <path d="M20 31h24" />
      <path d="M32 24v-3" />
    </>
  ),
  "dehydration-deficit": (
    <>
      <path d="M32 4c-8 10-13 16-13 23a13 13 0 0 0 26 0c0-7-5-13-13-23z" />
      <path d="M22 29c3 2 6 2 10 0s7-2 10 0" />
    </>
  ),
  "daily-fluid-need": (
    <>
      <rect x="18" y="4" width="28" height="30" rx="7" />
      <path d="M26 4V2h12v2M24 20c3 2 5 2 8 0s5-2 8 0M32 34v10" />
    </>
  ),
  "infusion-rate": (
    <>
      <rect x="6" y="6" width="22" height="26" rx="6" />
      <path d="M14 22c2 1.5 4 1.5 6 0M17 32v6h22" />
      <circle cx="48" cy="38" r="10" />
      <path d="M48 32v6l4 2" />
    </>
  ),
  "drip-rate": (
    <>
      <path d="M32 2v6" />
      <rect x="22" y="8" width="20" height="24" rx="5" />
      <path d="M32 14c-3.5 4-3.5 7 0 7s3.5-3 0-7z" />
      <path d="M32 32v14" />
    </>
  ),
  cri: (
    <>
      <rect x="10" y="17" width="30" height="14" rx="3" />
      <path d="M10 24H4M4 19v10M40 24h18M18 17v4M25 17v4M32 17v4" />
      <path d="M44 38c3 0 5-2 7-5" />
    </>
  ),
  "flock-water-dose": (
    <>
      <ellipse cx="26" cy="28" rx="15" ry="10" />
      <circle cx="43" cy="17" r="5" />
      <path d="M48 17l6 2M23 38v6M30 38v6M12 25l-6-4" />
      <path d="M56 30c-3 4-3 7 0 7s3-3 0-7z" />
    </>
  ),
  "withdrawal-date": (
    <>
      <rect x="10" y="9" width="44" height="34" rx="5" />
      <path d="M10 19h44M20 4v8M44 4v8M23 31l6 6 12-12" />
    </>
  ),
};

const FALLBACK = (
  <>
    <rect x="16" y="6" width="32" height="36" rx="5" />
    <path d="M23 14h18M23 24h4M31 24h4M39 24h2M23 32h4M31 32h4M39 32h2" />
  </>
);

export function CalcArt({
  slug,
  tone = "violet",
  className = "h-12 w-16",
}: {
  slug: string;
  tone?: Tone;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 64 48"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`tone-${tone} shrink-0 text-[var(--tone)] ${className}`}
    >
      {ART[slug] ?? FALLBACK}
    </svg>
  );
}
