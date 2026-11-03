/**
 * Country flags are the real SVGs from the `flag-icons` package (MIT), copied to /public/flags by
 * scripts/build-country-assets.mjs, one file per ISO 3166-1 alpha-2 code.
 */

/** A thin accent line drawn from a country's flag colours. Data, not a branch on the country code. */
const ACCENTS: Record<string, string> = {
  IN: "linear-gradient(90deg,#ff9933 0 33.3%,#ffffff 33.3% 66.6%,#138808 66.6%)",
  PK: "linear-gradient(90deg,#ffffff 0 25%,#01411c 25%)",
  AE: "linear-gradient(90deg,#00732f 0 33.3%,#ffffff 33.3% 66.6%,#000000 66.6%)",
  GB: "linear-gradient(90deg,#012169 0 33.3%,#ffffff 33.3% 66.6%,#c8102e 66.6%)",
  US: "linear-gradient(90deg,#b22234 0 33.3%,#ffffff 33.3% 66.6%,#3c3b6e 66.6%)",
  CA: "linear-gradient(90deg,#d52b1e 0 25%,#ffffff 25% 75%,#d52b1e 75%)",
  AU: "linear-gradient(90deg,#012169 0 50%,#e4002b 50%)",
};

export function flagAccent(iso2: string): string | undefined {
  return ACCENTS[iso2.toUpperCase()];
}

export function Flag({
  iso2,
  name,
  className = "h-8 w-12",
}: {
  iso2: string;
  /** Country name for the alt text; omit when the name is printed right beside the flag. */
  name?: string;
  className?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- static SVG, nothing to optimise
    <img
      src={`/flags/${iso2.toLowerCase()}.svg`}
      alt={name ? `Flag of ${name}` : ""}
      width={48}
      height={36}
      loading="lazy"
      className={`shrink-0 rounded-[3px] object-cover shadow-[0_0_0_1px_rgba(0,0,0,0.12)] ${className}`}
    />
  );
}
