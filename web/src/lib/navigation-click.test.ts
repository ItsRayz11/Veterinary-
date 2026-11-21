import { describe, expect, it } from "vitest";
import { startsNavigation, type ClickInfo, type LinkInfo } from "./navigation-click";

const click: ClickInfo = {
  defaultPrevented: false,
  button: 0,
  metaKey: false,
  ctrlKey: false,
  shiftKey: false,
  altKey: false,
};
const link = (href: string, extra: Partial<LinkInfo> = {}): LinkInfo => ({
  href,
  target: "",
  hasDownload: false,
  ...extra,
});
const HERE = "https://site.test/species?x=1";

describe("startsNavigation", () => {
  it("is true for a normal link to another page or another query", () => {
    expect(startsNavigation(click, link("https://site.test/jobs"), HERE)).toBe(true);
    expect(startsNavigation(click, link("https://site.test/species?x=2"), HERE)).toBe(true);
    expect(startsNavigation(click, link("https://site.test/search?q=a%20b"), HERE)).toBe(true);
  });

  it("is false when the link points at the page already shown, hash or not", () => {
    expect(startsNavigation(click, link("https://site.test/species?x=1"), HERE)).toBe(false);
    expect(startsNavigation(click, link("https://site.test/species?x=1#top"), HERE)).toBe(false);
  });

  it("ignores other origins, new tabs, downloads and handled clicks", () => {
    expect(startsNavigation(click, link("https://other.test/jobs"), HERE)).toBe(false);
    expect(
      startsNavigation(click, link("https://site.test/jobs", { target: "_blank" }), HERE),
    ).toBe(false);
    expect(
      startsNavigation(click, link("https://site.test/a.pdf", { hasDownload: true }), HERE),
    ).toBe(false);
    expect(
      startsNavigation({ ...click, defaultPrevented: true }, link("https://site.test/jobs"), HERE),
    ).toBe(false);
  });

  it("ignores modified and non-primary clicks (open in new tab/window, middle button)", () => {
    for (const mod of [
      { metaKey: true },
      { ctrlKey: true },
      { shiftKey: true },
      { altKey: true },
      { button: 1 },
    ]) {
      expect(startsNavigation({ ...click, ...mod }, link("https://site.test/jobs"), HERE)).toBe(
        false,
      );
    }
  });

  it("treats target=_self like no target and survives malformed URLs", () => {
    expect(startsNavigation(click, link("https://site.test/jobs", { target: "_self" }), HERE)).toBe(
      true,
    );
    expect(startsNavigation(click, link("not a url"), HERE)).toBe(false);
    expect(startsNavigation(click, link("https://site.test/jobs"), "also not a url")).toBe(false);
  });
});
