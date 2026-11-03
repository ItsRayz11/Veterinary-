/**
 * Outline of a country drawn from Natural Earth boundaries (public domain), see /credits. It is an
 * orientation graphic, not an authoritative political boundary.
 */
export function CountryMap({ iso2, name }: { iso2: string; name: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- static SVG, nothing to optimise
    <img
      src={`/maps/${iso2.toLowerCase()}.svg`}
      alt={`Outline map of ${name}`}
      width={400}
      height={300}
      loading="lazy"
      className="h-auto w-full max-w-[22rem] drop-shadow-[0_6px_12px_rgba(11,52,55,0.18)]"
    />
  );
}
