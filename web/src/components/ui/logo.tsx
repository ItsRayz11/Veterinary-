/**
 * Wordmark plus a flat mark drawn from the site's review mark: a ring (a record) around a filled
 * dot (reviewed). One solid colour, no gradient.
 */
export function Logo() {
  return (
    <span className="inline-flex items-center gap-2 text-primary">
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true" className="shrink-0">
        <circle cx="11" cy="11" r="9.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="11" cy="11" r="4" fill="currentColor" />
      </svg>
      <span className="text-[17px] font-semibold leading-none tracking-[-0.01em] text-text">
        VetRef
      </span>
    </span>
  );
}
