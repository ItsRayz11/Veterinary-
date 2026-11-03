import type { ReactNode } from "react";

/**
 * Flags drawn as SVG for countries whose flag is simple and unambiguous. Any other country falls
 * back to an ISO monogram, so nothing is ever shown with the wrong flag. `accent` is the only
 * country-specific styling the hero applies.
 */
const FLAGS: Record<string, { svg: ReactNode; accent: string }> = {
  IN: {
    accent: "linear-gradient(90deg,#ff9933 0 33.3%,#ffffff 33.3% 66.6%,#138808 66.6%)",
    svg: (
      <>
        <rect width="30" height="6.67" fill="#ff9933" />
        <rect y="6.67" width="30" height="6.66" fill="#fff" />
        <rect y="13.33" width="30" height="6.67" fill="#138808" />
        <g stroke="#000080" strokeWidth=".3" fill="none">
          <circle cx="15" cy="10" r="2.9" strokeWidth=".5" />
          {Array.from({ length: 12 }, (_, i) => {
            const a = (i * Math.PI) / 12;
            const dx = Math.cos(a) * 2.9;
            const dy = Math.sin(a) * 2.9;
            return <line key={i} x1={15 - dx} y1={10 - dy} x2={15 + dx} y2={10 + dy} />;
          })}
        </g>
      </>
    ),
  },
};

export function flagAccent(iso2: string): string | undefined {
  return FLAGS[iso2.toUpperCase()]?.accent;
}

export function Flag({ iso2, className = "h-8 w-12" }: { iso2: string; className?: string }) {
  const f = FLAGS[iso2.toUpperCase()];
  if (!f) {
    return (
      <span
        aria-hidden="true"
        className={`icon-chip tone-green rounded-md text-xs font-semibold tracking-wide ${className}`}
      >
        {iso2.toUpperCase()}
      </span>
    );
  }
  return (
    <svg
      viewBox="0 0 30 20"
      aria-hidden="true"
      className={`shrink-0 rounded-[3px] shadow-[0_0_0_1px_rgba(0,0,0,0.12)] ${className}`}
    >
      {f.svg}
    </svg>
  );
}
