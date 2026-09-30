/** Pure helpers for `src/proxy.ts`, the same-origin bridge from /api/v1/* to the Django API. */

const IPV4 = /^(?:\d{1,3}\.){3}\d{1,3}$/;
const IPV6 = /^[0-9a-fA-F:]+(?:%[\w.-]+)?$/;

function validIp(value: string | null | undefined): string | null {
  const v = (value ?? "").trim();
  if (!v || v.length > 45) return null;
  if (IPV4.test(v) && v.split(".").every((n) => Number(n) <= 255)) return v;
  if (v.includes(":") && IPV6.test(v)) return v;
  return null;
}

/**
 * The real client address as set by the hosting edge. On Vercel `x-forwarded-for` is overwritten
 * with the client IP at the edge (its first entry is the client); `x-real-ip` is the fallback.
 * Self-hosting behind your own proxy: make sure it sets one of these and drops client-sent copies.
 */
export function clientIp(headers: Headers): string | null {
  return (
    validIp(headers.get("x-forwarded-for")?.split(",")[0]) ?? validIp(headers.get("x-real-ip"))
  );
}

/**
 * Request headers for the API. Any `x-client-ip` / `x-web-proxy-secret` the browser sent is
 * dropped first, so a client can never inject its own identity; the trusted pair is added only
 * when a secret is configured and a client address is known.
 */
export function upstreamHeaders(incoming: Headers, secret: string | undefined): Headers {
  const out = new Headers(incoming);
  out.delete("x-client-ip");
  out.delete("x-web-proxy-secret");
  const ip = clientIp(incoming);
  if (secret && ip) {
    out.set("x-client-ip", ip);
    out.set("x-web-proxy-secret", secret);
  }
  return out;
}

/** Django routes end with "/", Next strips it, so it is re-added here (query string kept). */
export function upstreamUrl(apiUrl: string, pathname: string, search: string): string {
  return `${apiUrl.replace(/\/+$/, "")}${pathname.replace(/\/+$/, "")}/${search}`;
}
