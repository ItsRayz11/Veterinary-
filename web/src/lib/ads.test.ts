import { describe, expect, it } from "vitest";
import { AD_ZONES, adsConfig, adsTxt } from "./ads";
import { contentSecurityPolicy } from "./security-headers";

describe("ads configuration", () => {
  it("is off by default", () => {
    expect(adsConfig({}).enabled).toBe(false);
    expect(adsConfig({ ADS_ENABLED: "true" }).enabled).toBe(false); // needs a publisher id
    expect(adsConfig({ ADSENSE_CLIENT: "ca-pub-1234567890" }).enabled).toBe(false);
  });

  it("needs both the switch and a well-formed publisher id", () => {
    const on = adsConfig({
      ADS_ENABLED: "true",
      ADSENSE_CLIENT: "ca-pub-1234567890",
      ADSENSE_SLOT_DIRECTORY: "1234567890",
      ADSENSE_SLOT_BLOG: "not-a-slot",
    });
    expect(on.enabled).toBe(true);
    expect(on.slots.directory).toBe("1234567890");
    expect(on.slots.blog).toBeUndefined();
    expect(adsConfig({ ADS_ENABLED: "true", ADSENSE_CLIENT: "x<script>" }).enabled).toBe(false);
  });

  it("has no clinical or regulatory ad zone", () => {
    for (const z of AD_ZONES) expect(z).not.toMatch(/clinic|dose|regulat|withdraw|calc|interact/);
  });

  it("serves ads.txt only with a publisher id", () => {
    expect(adsTxt({})).toBeNull();
    expect(adsTxt({ ADSENSE_CLIENT: "ca-pub-1234567890" })).toBe(
      "google.com, pub-1234567890, DIRECT, f08c47fec0942fa0\n",
    );
  });
});

describe("CSP with ads", () => {
  it("adds ad origins only when ads are enabled", () => {
    expect(contentSecurityPolicy(true, false)).not.toContain("googlesyndication");
    expect(contentSecurityPolicy(true, false)).not.toContain("frame-src");
    const csp = contentSecurityPolicy(true, true);
    expect(csp).toContain("https://pagead2.googlesyndication.com");
    expect(csp).toContain("frame-src");
    expect(csp).toContain("frame-ancestors 'none'");
  });
});
