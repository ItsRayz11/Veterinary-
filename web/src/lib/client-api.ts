/** Browser-side calls to the API through the same-origin /api/v1 rewrite (session cookies + CSRF). */

export class ClientApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

let csrfToken: string | null = null;

async function csrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  const res = await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  csrfToken = ((await res.json()) as { csrfToken: string }).csrfToken;
  return csrfToken;
}

/** Flattens the uniform error envelope / DRF field errors into a message plus per-field messages. */
function toError(status: number, body: unknown): ClientApiError {
  const fields: Record<string, string> = {};
  let message =
    status === 429 ? "Too many attempts. Please wait and try again." : "Request failed.";
  const b = body as Record<string, unknown> | null;
  const details =
    (b && typeof b === "object" && (b.error as Record<string, unknown> | undefined)?.details) || b;
  if (details && typeof details === "object") {
    for (const [k, v] of Object.entries(details as Record<string, unknown>)) {
      const text = Array.isArray(v) ? v.join(" ") : typeof v === "string" ? v : null;
      if (text) fields[k] = text;
    }
  }
  const envMsg = (b?.error as { message?: string } | undefined)?.message;
  if (envMsg && status !== 400) message = envMsg;
  else if (fields.non_field_errors || fields.detail)
    message = fields.non_field_errors ?? fields.detail;
  return new ClientApiError(message, status, fields);
}

export async function apiSend<T = unknown>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": await csrf() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 403) csrfToken = null; // stale token: refetch next time
    throw toError(res.status, data);
  }
  return data as T;
}

export async function apiFetch<T>(path: string): Promise<T | null> {
  const res = await fetch(`/api/v1${path}`, { credentials: "same-origin" });
  if (res.status === 401 || res.status === 403) return null;
  if (!res.ok) throw new ClientApiError("Request failed.", res.status);
  return (await res.json()) as T;
}
