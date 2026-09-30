/** Security headers for every page. Kept in src/ so tests can check the policy. */

export function contentSecurityPolicy(production: boolean): string {
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    // Next.js emits small inline bootstrap scripts; dev also needs eval for fast refresh.
    "script-src": ["'self'", "'unsafe-inline'", ...(production ? [] : ["'unsafe-eval'"])],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'", "data:"],
    // The browser only talks to this origin; the API is reached through the /api/v1 rewrite.
    "connect-src": ["'self'"],
    "worker-src": ["'self'"],
    "manifest-src": ["'self'"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "object-src": ["'none'"],
  };
  return Object.entries(directives)
    .map(([k, v]) => `${k} ${v.join(" ")}`)
    .join("; ");
}

export function securityHeaders(production: boolean) {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(production) },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    // No includeSubDomains/preload: those are a domain-wide decision (docs/SECURITY.md).
    { key: "Strict-Transport-Security", value: "max-age=31536000" },
  ];
}
