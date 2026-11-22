import { describe, expect, it } from "vitest";
import { breadcrumbJsonLd } from "./primitives";

describe("breadcrumbJsonLd (Google: item required except on the last crumb)", () => {
  it("keeps every crumb that has a URL and the last crumb without one", () => {
    const j = breadcrumbJsonLd([
      { label: "Home", href: "/" },
      { label: "Articles", href: "/blog" },
      { label: "A post" },
    ]);
    expect(j.itemListElement.map((e) => e.position)).toEqual([1, 2, 3]);
    expect("item" in j.itemListElement[2]).toBe(false);
  });
  it("drops a middle crumb without a URL and renumbers", () => {
    const j = breadcrumbJsonLd([
      { label: "Home", href: "/" },
      { label: "Companies" },
      { label: "Acme" },
    ]);
    expect(j.itemListElement.map((e) => e.name)).toEqual(["Home", "Acme"]);
    expect(j.itemListElement.map((e) => e.position)).toEqual([1, 2]);
    for (const e of j.itemListElement.slice(0, -1)) expect("item" in e).toBe(true);
  });
});
