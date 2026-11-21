import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Status } from "@/lib/api";
import { StatusLine } from "./status-line";

/**
 * Review-status invariants from docs/CLINICAL_GOVERNANCE.md as the visitor sees them: unreviewed,
 * imported or development data must never carry a "Verified" or "Expert reviewed" badge, whatever
 * combination of fields the API sends. Text only (never colour alone), so these read as labels.
 */
const status = (over: Partial<Status>): Status => ({
  code: "verified",
  label: "x",
  is_development_data: false,
  reviewed_at: "2026-01-15",
  ...over,
});
const text = (s: Status) =>
  renderToStaticMarkup(<StatusLine status={s} />).replace(/<[^>]+>/g, " ");
const hasReviewedBadge = (t: string) => /\bVerified\b|\bExpert reviewed\b/.test(t);

describe("StatusLine labels", () => {
  it.each([
    ["verified", "Verified"],
    ["expert_reviewed", "Expert reviewed"],
    ["official_regulatory", "Official listing, not clinically reviewed"],
    ["manufacturer_supplied", "Manufacturer supplied"],
    ["source_found_pending_review", "Pending review"],
    ["needs_verification", "Needs verification"],
    ["imported_unverified", "Imported, not reviewed"],
    ["deprecated", "Deprecated"],
  ])("%s is shown as %s", (code, label) => {
    expect(text(status({ code }))).toContain(label);
  });

  it("falls back to 'Needs verification', never to a reviewed label, for an unknown code", () => {
    const t = text(status({ code: "something_new" }));
    expect(t).toContain("Needs verification");
    expect(hasReviewedBadge(t)).toBe(false);
  });
});

describe("a reviewed badge is impossible for unreviewed data", () => {
  const REVIEWED_CODES = ["verified", "expert_reviewed"];

  it.each(REVIEWED_CODES)(
    "development data wins over the code %s: shown as development, not verified",
    (code) => {
      const t = text(status({ code, is_development_data: true }));
      expect(t).toContain("Development data, not verified");
      expect(hasReviewedBadge(t)).toBe(false);
    },
  );

  it.each(REVIEWED_CODES)(
    "an unverified import is never shown as reviewed, even if the code says %s",
    (code) => {
      const t = text(status({ code, is_unverified_import: true }));
      expect(t).toContain("Imported, not reviewed");
      expect(hasReviewedBadge(t)).toBe(false);
    },
  );

  it("does not print a 'Reviewed <date>' line for development, imported or official-listing data", () => {
    for (const over of [
      { is_development_data: true },
      { is_unverified_import: true },
      { tier: "official_listing" },
    ]) {
      expect(text(status(over))).not.toContain("Reviewed 2026");
    }
  });

  it("does print the review date for a genuinely reviewed record", () => {
    expect(text(status({ code: "expert_reviewed" }))).toMatch(/Reviewed/);
  });
});
