import { DESKTOP_NAV_MIN_WIDTH, headerSignIn, ROUTES, WIDTHS } from "./helpers";
import { expect, test } from "./fixtures";

/**
 * Regression for the Phase 1 defect: the 7-item top nav appeared at 640px but needs about 910px,
 * so every page overflowed sideways between 640 and 900px. Measured with real layout numbers, one
 * test per width and route so a failure names the exact page and a slow engine never hits a
 * timeout. Invariants are polled (they must settle to "no violations") because layout can still
 * shift for a moment after load on a loaded machine; a persistent problem still fails.
 */
for (const width of WIDTHS) {
  test.describe(`at ${width}px`, () => {
    test.use({ viewport: { width, height: 800 } });
    const desktop = width >= DESKTOP_NAV_MIN_WIDTH;

    for (const route of ROUTES) {
      test(`${route}: no overflow, one nav, nothing covered, readable targets`, async ({
        page,
      }) => {
        await page.goto(route);
        await expect(headerSignIn(page)).toBeVisible();

        const violations = () =>
          page.evaluate(
            async ({ desktop }) => {
              const out: string[] = [];
              const visible = (e: Element | null) =>
                !!e &&
                getComputedStyle(e).display !== "none" &&
                e.getBoundingClientRect().width > 0;
              const frame = () => new Promise((r) => requestAnimationFrame(() => r(null)));
              const de = document.documentElement;
              const top = document.querySelector('nav[aria-label="Primary"]');
              const bottom = document.querySelector('nav[aria-label="Mobile"]');
              const footer = document.querySelector("footer");

              de.style.scrollBehavior = "auto";
              window.scrollTo(0, de.scrollHeight);
              await frame();
              await frame();

              const overflow = de.scrollWidth - de.clientWidth;
              if (overflow > 0) out.push(`horizontal overflow ${overflow}px`);
              if (visible(top) !== desktop) out.push(`top nav visible=${visible(top)}`);
              if (visible(bottom) === desktop)
                out.push(`bottom tab bar visible=${visible(bottom)}`);
              // The footer (site map, credits) is shown at every width since the redesign.
              if (!visible(footer)) out.push("footer hidden");

              const main = document.querySelector("main")!;
              const lastContentBottom = Math.max(
                ...[...main.querySelectorAll("*")]
                  .filter((e) => e.getBoundingClientRect().height > 0)
                  .map((e) => e.getBoundingClientRect().bottom),
              );
              if (visible(bottom)) {
                const covered = Math.round(lastContentBottom - bottom!.getBoundingClientRect().top);
                if (covered > 0) out.push(`content hidden behind the tab bar by ${covered}px`);
                // Scrolled to the end, the footer's last line must clear the fixed tab bar.
                const lastFooterLine = Math.max(
                  ...[...footer!.querySelectorAll("a, span, p")]
                    .filter((e) => e.getBoundingClientRect().height > 0)
                    .map((e) => e.getBoundingClientRect().bottom),
                );
                const footerCovered = Math.round(
                  lastFooterLine - bottom!.getBoundingClientRect().top,
                );
                if (footerCovered > 0)
                  out.push(`footer hidden behind the tab bar by ${footerCovered}px`);
              }

              const small = (sel: string, what: string) =>
                [...document.querySelectorAll(sel)].forEach((e) => {
                  const r = e.getBoundingClientRect();
                  if (r.height < 44 || r.width < 44) {
                    out.push(
                      `${what} "${(e.textContent ?? "").trim()}" is ${Math.round(r.width)}x${Math.round(r.height)} (<44)`,
                    );
                  }
                });
              small("header a[href='/login'], header a[href='/register']", "auth link");
              if (visible(bottom)) small('nav[aria-label="Mobile"] a', "tab");

              if (visible(bottom)) {
                for (const s of document.querySelectorAll('nav[aria-label="Mobile"] a span')) {
                  if (visible(s) && s.scrollWidth > s.clientWidth + 0.5) {
                    out.push(`tab label "${s.textContent}" is truncated`);
                  }
                }
              }
              return out;
            },
            { desktop },
          );

        await expect
          .poll(violations, { timeout: 10_000, message: `${route} @ ${width}px` })
          .toEqual([]);
      });
    }
  });
}
