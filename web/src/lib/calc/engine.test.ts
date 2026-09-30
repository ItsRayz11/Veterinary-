import { readFileSync } from "node:fs";
import path from "node:path";
import Decimal from "decimal.js";
import { describe, expect, it } from "vitest";
import { CalcError, ENGINE, dose_calc, roundDisplay, withdrawal_end } from "./engine";

interface Case {
  name: string;
  fn: keyof typeof ENGINE;
  input: Record<string, string>;
  expected?: Record<string, string>;
  error?: boolean;
}

const cases: Case[] = JSON.parse(
  readFileSync(path.resolve(__dirname, "../../../../shared/calc-vectors.json"), "utf-8"),
).cases;

describe("shared calculator vectors", () => {
  it.each(cases.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    const fn = ENGINE[c.fn] as unknown as (input: Record<string, string>) => {
      values: Record<string, Decimal>;
    };
    if (c.error) {
      expect(() => fn(c.input)).toThrow(CalcError);
      return;
    }
    const r = fn(c.input);
    for (const [key, expected] of Object.entries(c.expected ?? {})) {
      expect(r.values[key].equals(new Decimal(expected)), `${key}: ${r.values[key]}`).toBe(true);
    }
  });
});

describe("engine behaviour", () => {
  it("warns above maximum dose without clipping", () => {
    const r = dose_calc({
      weight: 500,
      dose_mg_per_kg: 10,
      concentration_mg_per_ml: 100,
      max_dose_mg: 3000,
    });
    expect(r.values.total_mg.toString()).toBe("5000");
    expect(r.warnings[0]).toContain("exceeds");
  });

  it("has no float drift", () => {
    expect(
      ENGINE.mg_to_ml({
        dose_mg: "0.3",
        concentration_mg_per_ml: "0.1",
      }).values.volume_ml.toString(),
    ).toBe("3");
  });

  it("rounds half up for display", () => {
    expect(roundDisplay(new Decimal("2.675"), 2)).toBe("2.68");
  });

  it("computes withdrawal end", () => {
    const r = withdrawal_end({
      last_treatment: new Date("2026-01-01T08:00:00Z"),
      withdrawal_hours: 96,
    });
    expect(r.eligible_from?.toISOString()).toBe("2026-01-05T08:00:00.000Z");
  });
});
