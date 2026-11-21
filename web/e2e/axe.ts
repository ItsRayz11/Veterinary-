import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect } from "./fixtures";

/** Runs axe-core (WCAG 2.0/2.1/2.2 A and AA plus best-practice) and fails with a readable summary. */
export async function scan(page: Page, label: string) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  const summary = violations.map(
    (v) => `[${v.impact}] ${v.id} (${v.nodes.length}): ${v.nodes[0]?.target.join(" ")}`,
  );
  expect(summary, `axe violations on ${label}`).toEqual([]);
}
