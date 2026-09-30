/**
 * Where to go after signing in. Only same-origin paths are honoured; anything else falls back to
 * "/". The value is resolved with the URL parser (the same one the browser uses) instead of string
 * checks, because browsers treat "\" as "/" and ignore tabs/newlines, so "/\evil.com" and
 * "/\t/evil.com" both mean "//evil.com" (another site).
 */
export function safeNext(raw: string | null, origin: string): string {
  if (!raw || !raw.startsWith("/")) return "/";
  try {
    const url = new URL(raw, origin);
    if (url.origin !== origin) return "/";
    return url.pathname + url.search + url.hash;
  } catch {
    return "/";
  }
}
