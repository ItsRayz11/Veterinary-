/**
 * Sends browser errors to our own API (see api/apps/monitoring). The server scrubs emails and
 * tokens, drops query strings and stores no user identity; this side keeps the volume low:
 * identical errors are sent once per page load and at most MAX_PER_PAGE in total.
 */

export const MAX_PER_PAGE = 5;
const sent = new Set<string>();

export function resetReporter() {
  sent.clear();
}

function toError(value: unknown): Error {
  if (value instanceof Error) return value;
  try {
    return new Error(typeof value === "string" ? value : JSON.stringify(value));
  } catch {
    return new Error("Unknown error");
  }
}

/** Noise that says nothing useful about our code. */
export function isNoise(message: string): boolean {
  return (
    /^Script error\.?$/i.test(message) ||
    /ResizeObserver loop/i.test(message) ||
    /Failed to fetch|NetworkError|Load failed|AbortError/i.test(message) // offline / cancelled
  );
}

export function reportError(value: unknown, context?: string): boolean {
  if (typeof window === "undefined" || sent.size >= MAX_PER_PAGE) return false;
  const error = toError(value);
  if (!error.message || isNoise(error.message)) return false;
  const key = `${error.message}|${(error.stack ?? "").split("\n")[1] ?? ""}`;
  if (sent.has(key)) return false;
  sent.add(key);
  const body = JSON.stringify({
    message: context ? `${context}: ${error.message}` : error.message,
    stack: error.stack ?? "",
    url: window.location.href,
    release: process.env.NEXT_PUBLIC_RELEASE ?? "",
  });
  fetch("/api/v1/monitoring/client-errors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {
    // Reporting must never cause errors of its own.
  });
  return true;
}
