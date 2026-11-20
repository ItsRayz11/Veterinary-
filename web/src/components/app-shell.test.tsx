import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: () => {}, refresh: () => {} }),
}));
vi.mock("@/lib/use-user", () => ({ useUser: () => null, notifyAuthChanged: () => {} }));

import { AppShell } from "./app-shell";

const html = renderToStaticMarkup(<AppShell>content</AppShell>);

// Regression: at 640-959px the 7-item top nav (about 910px wide) overflowed the page by 140px.
// Layout itself is proven by the browser width audit; these guard the breakpoint pairing.
describe("AppShell responsive chrome", () => {
  it("shows the top nav only from lg, never from sm", () => {
    const nav = html.match(/<nav aria-label="Primary"[^>]*>/)![0];
    expect(nav).toContain("lg:flex");
    expect(nav).not.toContain("sm:flex");
  });

  it("swaps the mobile tab bar out at the same breakpoint, so the two never overlap or both vanish", () => {
    const nav = html.match(/<nav aria-label="Mobile"[^>]*>/)![0];
    expect(nav).toContain("lg:hidden");
    expect(nav).not.toContain("sm:hidden");
  });

  it("only drops the bottom padding reserved for the tab bar when the tab bar is hidden", () => {
    const main = html.match(/<main[^>]*>/)![0];
    expect(main).toContain("pb-24");
    expect(main).toContain("lg:pb-8");
    expect(main).not.toContain("sm:pb-8");
  });

  it("gives the sign-in and register links a touch-sized hit area", () => {
    for (const label of ["Sign in", "Register"]) {
      const link = html.match(new RegExp(`<a[^>]*>${label}</a>`))![0];
      expect(link).toContain("min-h-10");
    }
  });
});
