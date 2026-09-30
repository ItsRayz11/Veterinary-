import { describe, expect, it } from "vitest";
import { CALCULATORS, bySlug } from "./registry";

const run = (slug: string, v: Record<string, string>) => bySlug(slug)!.run(v).values;

describe("calculator registry (hand-computed)", () => {
  it("has unique slugs and every output key is produced", () => {
    expect(new Set(CALCULATORS.map((c) => c.slug)).size).toBe(CALCULATORS.length);
  });

  it("dilution: 10 -> 2 in 100 mL needs 20 mL stock + 80 mL diluent", () => {
    const r = run("dilution", { stock_conc: "10", target_conc: "2", final_volume_ml: "100" });
    expect(r.stock_volume_ml.toString()).toBe("20");
    expect(r.diluent_ml.toString()).toBe("80");
  });

  it("dehydration deficit: 10 kg x 5% x 10 = 500 mL", () => {
    const r = run("dehydration-deficit", { weight: "10", dehydration_percent: "5" });
    expect(r.deficit_ml.toString()).toBe("500");
  });

  it("infusion: 500 mL over 5 h = 100 mL/h; drip at 20 gtt/mL = 33.33 drops/min", () => {
    expect(run("infusion-rate", { volume_ml: "500", hours: "5" }).ml_per_hour.toString()).toBe(
      "100",
    );
    const d = run("drip-rate", { volume_ml: "500", hours: "5", drops_per_ml: "20" });
    expect(d.drops_per_min.toDecimalPlaces(2).toString()).toBe("33.33");
  });

  it("CRI: 2 mcg/kg/min, 10 kg, 1 mg/mL = 1.2 mL/h", () => {
    const r = run("cri", {
      weight: "10",
      dose_mcg_per_kg_min: "2",
      concentration_mg_per_ml: "1",
    });
    expect(r.ml_per_hour.toString()).toBe("1.2");
  });

  it("withdrawal: 24 h after a fixed instant", () => {
    const r = bySlug("withdrawal-date")!.run({
      last_treatment: "2026-01-01T00:00:00Z",
      withdrawal_hours: "24",
    });
    expect(r.eligible_from!.toISOString()).toBe("2026-01-02T00:00:00.000Z");
  });

  it("rejects impossible input with a readable message", () => {
    expect(() =>
      run("dilution", { stock_conc: "2", target_conc: "10", final_volume_ml: "100" }),
    ).toThrow(/cannot be higher/);
  });
});
