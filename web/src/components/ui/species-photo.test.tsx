import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import credits from "@/lib/image-credits.json";
import { SpeciesCard, SpeciesPhoto } from "./species-photo";

const slug = Object.keys((credits as { species: Record<string, unknown> }).species)[0];

describe("species photo alt text", () => {
  it("a card, which already prints the name, marks the photo decorative (no duplicate announcement)", () => {
    const html = renderToStaticMarkup(<SpeciesCard slug={slug} name="Cattle" />);
    expect(html).toContain('alt=""');
    expect(html).toContain("Cattle");
  });
  it("a standalone photo keeps the species name as its alt text", () => {
    const html = renderToStaticMarkup(<SpeciesPhoto slug={slug} name="Cattle" />);
    expect(html).toContain('alt="Cattle"');
  });
});
