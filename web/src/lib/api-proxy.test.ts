import { describe, expect, it } from "vitest";
import { clientIp, upstreamHeaders, upstreamUrl } from "./api-proxy";

const h = (o: Record<string, string>) => new Headers(o);

describe("clientIp", () => {
  it("uses the first x-forwarded-for entry, then x-real-ip", () => {
    expect(clientIp(h({ "x-forwarded-for": "203.0.113.7, 10.0.0.1" }))).toBe("203.0.113.7");
    expect(clientIp(h({ "x-real-ip": "198.51.100.4" }))).toBe("198.51.100.4");
    expect(clientIp(h({ "x-forwarded-for": "2001:db8::1" }))).toBe("2001:db8::1");
  });

  it.each(["", "not-an-ip", "999.1.1.1", "1.2.3", "<script>", "1.2.3.4.5", "a".repeat(60)])(
    "rejects %j",
    (bad) => {
      expect(clientIp(h({ "x-forwarded-for": bad }))).toBeNull();
    },
  );

  it("is null when the edge provided nothing", () => {
    expect(clientIp(h({}))).toBeNull();
  });
});

describe("upstreamHeaders", () => {
  it("adds the trusted pair only when a secret is configured and the client IP is known", () => {
    const out = upstreamHeaders(h({ "x-forwarded-for": "203.0.113.7" }), "s3cret");
    expect(out.get("x-client-ip")).toBe("203.0.113.7");
    expect(out.get("x-web-proxy-secret")).toBe("s3cret");
    const noSecret = upstreamHeaders(h({ "x-forwarded-for": "203.0.113.7" }), undefined);
    expect(noSecret.get("x-client-ip")).toBeNull();
    expect(noSecret.get("x-web-proxy-secret")).toBeNull();
    const noIp = upstreamHeaders(h({}), "s3cret");
    expect(noIp.get("x-web-proxy-secret")).toBeNull();
  });

  it("never lets the browser inject its own identity or the secret", () => {
    const evil = h({
      "x-client-ip": "1.1.1.1",
      "x-web-proxy-secret": "guessed",
      "x-forwarded-for": "203.0.113.7",
    });
    const withSecret = upstreamHeaders(evil, "real");
    expect(withSecret.get("x-client-ip")).toBe("203.0.113.7"); // from the edge, not the client's copy
    expect(withSecret.get("x-web-proxy-secret")).toBe("real");
    const withoutSecret = upstreamHeaders(evil, undefined);
    expect(withoutSecret.get("x-client-ip")).toBeNull();
    expect(withoutSecret.get("x-web-proxy-secret")).toBeNull();
  });

  it("keeps ordinary headers such as cookies and CSRF tokens", () => {
    const out = upstreamHeaders(h({ cookie: "sessionid=abc", "x-csrftoken": "t" }), "s");
    expect(out.get("cookie")).toBe("sessionid=abc");
    expect(out.get("x-csrftoken")).toBe("t");
  });
});

describe("upstreamUrl", () => {
  it("re-adds the trailing slash Django needs and keeps the query", () => {
    expect(upstreamUrl("http://api.test", "/api/v1/auth/me", "")).toBe(
      "http://api.test/api/v1/auth/me/",
    );
    expect(upstreamUrl("http://api.test/", "/api/v1/search/", "?q=enro")).toBe(
      "http://api.test/api/v1/search/?q=enro",
    );
  });
});
