import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** WCAG 2.x contrast ratio between two #rrggbb colours. */
function luminance(hex: string): number {
  const c = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
const ratio = (a: string, b: string) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

const css = readFileSync(join(process.cwd(), "src/app/globals.css"), "utf8");

function tokens(block: string): Record<string, string> {
  return Object.fromEntries(
    [...block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]),
  );
}
const light = tokens(css.slice(0, css.indexOf("@media")));
const dark = tokens(css.slice(css.indexOf("prefers-color-scheme: dark"), css.indexOf("@theme")));

// Every foreground/background pair the UI actually renders text with (AA body text = 4.5).
const PAIRS: [string, string][] = [
  ["text", "bg"],
  ["text", "surface"],
  ["text", "surface-2"],
  ["text-muted", "bg"],
  ["text-muted", "surface"],
  ["text-muted", "surface-2"],
  ["primary", "bg"],
  ["primary", "surface"],
  ["primary-fg", "primary"],
  ["ok", "ok-bg"],
  ["warn", "warn-bg"],
  ["danger", "danger-bg"],
  ["info", "info-bg"],
  ["danger", "surface"],
  ["ok", "surface"],
  ["warn", "surface"],
];

describe.each([
  ["light", light],
  ["dark", dark],
] as const)("%s theme contrast (WCAG AA 4.5:1)", (_name, palette) => {
  const merged = { ...(_name === "dark" ? light : {}), ...palette };
  it.each(PAIRS)("%s on %s", (fg, bg) => {
    expect(merged[fg], `missing token ${fg}`).toBeTruthy();
    expect(merged[bg], `missing token ${bg}`).toBeTruthy();
    expect(ratio(merged[fg], merged[bg])).toBeGreaterThanOrEqual(4.5);
  });
});
