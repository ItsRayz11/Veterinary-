import { describe, expect, it } from "vitest";
import { contentSecurityPolicy, securityHeaders } from "./security-headers";

describe("security headers", () => {
  const csp = contentSecurityPolicy(true);

  it("locks framing, plugins and base/form targets", () => {
    for (const d of [
      "frame-ancestors 'none'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ])
      expect(csp).toContain(d);
  });

  it("only allows same-origin network access and no remote scripts", () => {
    expect(csp).toContain("connect-src 'self'");
    expect(csp).toContain("default-src 'self'");
    expect(csp).not.toMatch(/https?:\/\//);
    expect(csp).not.toContain("'unsafe-eval'"); // production only
  });

  it("allows eval only outside production (fast refresh)", () => {
    expect(contentSecurityPolicy(false)).toContain("'unsafe-eval'");
  });

  it("sets the standard hardening headers", () => {
    const h = Object.fromEntries(securityHeaders(true).map((x) => [x.key, x.value]));
    expect(h["X-Content-Type-Options"]).toBe("nosniff");
    expect(h["X-Frame-Options"]).toBe("DENY");
    expect(h["Referrer-Policy"]).toBeTruthy();
    expect(h["Permissions-Policy"]).toContain("camera=()");
    expect(h["Strict-Transport-Security"]).not.toContain("preload");
  });
});
