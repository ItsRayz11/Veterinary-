/** Security headers for every page. Kept in src/ so tests can check the policy. */
import { AD_CSP } from "./ads";

/** `ads` adds the AdSense origins and nothing else; it is false unless an owner enabled ads. */
export function contentSecurityPolicy(production: boolean, ads = false): string {
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    // Next.js emits small inline bootstrap scripts; dev also needs eval for fast refresh.
    "script-src": [
      "'self'",
      "'unsafe-inline'",
      ...(production ? [] : ["'unsafe-eval'"]),
      ...(ads ? AD_CSP.script : []),
    ],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:", ...(ads ? AD_CSP.img : [])],
    "font-src": ["'self'", "data:"],
    // The browser only talks to this origin; the API is reached through the /api/v1 rewrite.
    // blob: lets the 3D viewer read the model it just fetched; no remote origin is allowed.
    "connect-src": ["'self'", "blob:", ...(ads ? AD_CSP.connect : [])],
    ...(ads ? { "frame-src": [...AD_CSP.frame] } : {}),
    "worker-src": ["'self'", "blob:"],
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

export function securityHeaders(production: boolean, ads = false) {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(production, ads) },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    // No includeSubDomains/preload: those are a domain-wide decision (docs/SECURITY.md).
    { key: "Strict-Transport-Security", value: "max-age=31536000" },
  ];
}
