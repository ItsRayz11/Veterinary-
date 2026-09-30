/**
 * Deterministic clinical arithmetic (client mirror of api/apps/calculators/engine.py).
 * Pure functions, exact decimals, no clinical constants: rates and concentrations are inputs.
 * Both engines are tested against shared/calc-vectors.json. Field names are snake_case on purpose.
 */
import Decimal from "decimal.js";

Decimal.set({ precision: 28, rounding: Decimal.ROUND_HALF_UP });

export class CalcError extends Error {}

export interface CalcResult {
  formula: string;
  values: Record<string, Decimal>;
  steps: string[];
  warnings: string[];
  eligible_from?: Date;
}

type Num = string | number;

const LB_PER_KG = new Decimal("2.20462262185");
const WEIGHT_KG_RANGE: [Decimal, Decimal] = [new Decimal("0.001"), new Decimal("2000")];

function dec(value: Num, name: string): Decimal {
  if (typeof value === "string" && value.trim() === "")
    throw new CalcError(`${name} must be a number.`);
  let d: Decimal;
  try {
    d = new Decimal(value);
  } catch {
    throw new CalcError(`${name} must be a number.`);
  }
  if (!d.isFinite()) throw new CalcError(`${name} must be a finite number.`);
  return d;
}

function positive(value: Num, name: string): Decimal {
  const d = dec(value, name);
  if (d.lte(0)) throw new CalcError(`${name} must be greater than zero.`);
  return d;
}

export function roundDisplay(value: Decimal, places = 2): string {
  return value.toDecimalPlaces(places, Decimal.ROUND_HALF_UP).toFixed(places);
}

export function toKg(weight: Num, unit: "kg" | "lb" | "g" = "kg"): Decimal {
  const w = positive(weight, "Weight");
  const kg = unit === "kg" ? w : unit === "lb" ? w.div(LB_PER_KG) : w.div(1000);
  const [lo, hi] = WEIGHT_KG_RANGE;
  if (kg.lt(lo) || kg.gt(hi)) throw new CalcError(`Weight must be between ${lo} and ${hi} kg.`);
  return kg;
}

const result = (
  formula: string,
  values: Record<string, Decimal>,
  steps: string[],
  warnings: string[] = [],
): CalcResult => ({ formula, values, steps, warnings });

export function percent_to_mg_per_ml(a: { percent: Num }): CalcResult {
  const p = positive(a.percent, "Percent");
  if (p.gt(100)) throw new CalcError("Percent (w/v) cannot exceed 100.");
  const v = p.mul(10);
  return result("mg/mL = % (w/v) x 10", { mg_per_ml: v }, [`${p} x 10 = ${v} mg/mL`]);
}

export function mg_to_ml(a: { dose_mg: Num; concentration_mg_per_ml: Num }): CalcResult {
  const mg = positive(a.dose_mg, "Dose");
  const c = positive(a.concentration_mg_per_ml, "Concentration");
  const v = mg.div(c);
  return result("mL = mg / (mg/mL)", { volume_ml: v }, [`${mg} mg / ${c} mg/mL = ${v} mL`]);
}

export function ml_to_mg(a: { volume_ml: Num; concentration_mg_per_ml: Num }): CalcResult {
  const ml = positive(a.volume_ml, "Volume");
  const c = positive(a.concentration_mg_per_ml, "Concentration");
  const mg = ml.mul(c);
  return result("mg = mL x (mg/mL)", { dose_mg: mg }, [`${ml} mL x ${c} mg/mL = ${mg} mg`]);
}

export function dose_calc(a: {
  weight: Num;
  dose_mg_per_kg: Num;
  concentration_mg_per_ml: Num;
  weight_unit?: "kg" | "lb" | "g";
  max_dose_mg?: Num | null;
}): CalcResult {
  const unit = a.weight_unit ?? "kg";
  const kg = toKg(a.weight, unit);
  const rate = positive(a.dose_mg_per_kg, "Dose rate");
  const conc = positive(a.concentration_mg_per_ml, "Concentration");
  const total = kg.mul(rate);
  const volume = total.div(conc);
  const steps: string[] = [];
  if (unit !== "kg") steps.push(`Weight: ${a.weight} ${unit} = ${kg} kg`);
  steps.push(`Total dose: ${kg} kg x ${rate} mg/kg = ${total} mg`);
  steps.push(`Volume: ${total} mg / ${conc} mg/mL = ${volume} mL`);
  const warnings: string[] = [];
  if (a.max_dose_mg != null) {
    const cap = positive(a.max_dose_mg, "Maximum dose");
    if (total.gt(cap)) {
      warnings.push(
        `Calculated dose ${roundDisplay(total)} mg exceeds the referenced maximum of ${cap} mg. Verify before administering.`,
      );
    }
  }
  return result(
    "total mg = weight (kg) x dose (mg/kg); volume mL = total mg / concentration (mg/mL)",
    { weight_kg: kg, total_mg: total, volume_ml: volume },
    steps,
    warnings,
  );
}

export function dilution(a: {
  stock_conc: Num;
  target_conc: Num;
  final_volume_ml: Num;
}): CalcResult {
  const c1 = positive(a.stock_conc, "Stock concentration");
  const c2 = positive(a.target_conc, "Target");
  const v2 = positive(a.final_volume_ml, "Final volume");
  if (c2.gt(c1))
    throw new CalcError("Target concentration cannot be higher than the stock concentration.");
  const v1 = c2.mul(v2).div(c1);
  return result(
    "V1 = (C2 x V2) / C1; diluent = V2 - V1",
    { stock_volume_ml: v1, diluent_ml: v2.sub(v1) },
    [`V1 = (${c2} x ${v2}) / ${c1} = ${v1} mL`, `Diluent = ${v2} - ${v1} = ${v2.sub(v1)} mL`],
  );
}

export function dehydration_deficit(a: {
  weight: Num;
  dehydration_percent: Num;
  weight_unit?: "kg" | "lb" | "g";
}): CalcResult {
  const kg = toKg(a.weight, a.weight_unit ?? "kg");
  const pct = positive(a.dehydration_percent, "Dehydration");
  if (pct.gt(30))
    throw new CalcError("Dehydration above 30% is outside the calculator's input range.");
  const deficit = kg.mul(pct).mul(10);
  return result("deficit (mL) = weight (kg) x dehydration (%) x 10", { deficit_ml: deficit }, [
    `${kg} kg x ${pct}% x 10 = ${deficit} mL`,
  ]);
}

export function daily_fluid_need(a: {
  weight: Num;
  ml_per_kg_per_day: Num;
  weight_unit?: "kg" | "lb" | "g";
}): CalcResult {
  const kg = toKg(a.weight, a.weight_unit ?? "kg");
  const rate = positive(a.ml_per_kg_per_day, "Fluid rate");
  const ml = kg.mul(rate);
  return result(
    "mL/day = weight (kg) x rate (mL/kg/day)",
    { ml_per_day: ml, ml_per_hour: ml.div(24) },
    [`${kg} kg x ${rate} mL/kg/day = ${ml} mL/day`, `${ml} / 24 = ${ml.div(24)} mL/h`],
  );
}

export function infusion_rate(a: { volume_ml: Num; hours: Num }): CalcResult {
  const v = positive(a.volume_ml, "Volume");
  const h = positive(a.hours, "Duration");
  const rate = v.div(h);
  return result("mL/h = volume / hours", { ml_per_hour: rate }, [`${v} / ${h} = ${rate} mL/h`]);
}

export function drip_rate(a: { volume_ml: Num; hours: Num; drops_per_ml: Num }): CalcResult {
  const v = positive(a.volume_ml, "Volume");
  const h = positive(a.hours, "Duration");
  const df = positive(a.drops_per_ml, "Drop factor");
  const perMin = v.mul(df).div(h.mul(60));
  return result(
    "drops/min = volume (mL) x drop factor (gtt/mL) / (hours x 60)",
    { drops_per_min: perMin, seconds_per_drop: new Decimal(60).div(perMin) },
    [`${v} x ${df} / (${h} x 60) = ${perMin} drops/min`],
  );
}

export function cri_rate(a: {
  weight: Num;
  dose_mcg_per_kg_min: Num;
  concentration_mg_per_ml: Num;
  weight_unit?: "kg" | "lb" | "g";
}): CalcResult {
  const kg = toKg(a.weight, a.weight_unit ?? "kg");
  const dose = positive(a.dose_mcg_per_kg_min, "CRI dose");
  const conc = positive(a.concentration_mg_per_ml, "Concentration");
  const mcgPerHour = dose.mul(kg).mul(60);
  const mlPerHour = mcgPerHour.div(conc.mul(1000));
  return result(
    "mL/h = dose (mcg/kg/min) x weight (kg) x 60 / (concentration (mg/mL) x 1000)",
    { ml_per_hour: mlPerHour, mcg_per_hour: mcgPerHour },
    [
      `${dose} mcg/kg/min x ${kg} kg x 60 = ${mcgPerHour} mcg/h`,
      `${mcgPerHour} / (${conc} x 1000) = ${mlPerHour} mL/h`,
    ],
  );
}

export function drinking_water_dose(a: {
  birds: Num;
  avg_weight_kg: Num;
  dose_mg_per_kg: Num;
  water_litres_per_day: Num;
  product_mg_per_g: Num;
}): CalcResult {
  const n = positive(a.birds, "Number of birds");
  const bw = toKg(a.avg_weight_kg, "kg");
  const rate = positive(a.dose_mg_per_kg, "Dose rate");
  const water = positive(a.water_litres_per_day, "Daily water intake (whole flock)");
  const potency = positive(a.product_mg_per_g, "Product strength (mg active per g)");
  const total = n.mul(bw).mul(rate);
  const conc = total.div(water);
  const productG = total.div(potency);
  return result(
    "total mg = birds x avg weight (kg) x dose (mg/kg); mg/L = total mg / water (L/day); product g = total mg / strength (mg/g)",
    { total_mg_per_day: total, mg_per_litre: conc, product_g_per_day: productG },
    [
      `${n} x ${bw} kg x ${rate} mg/kg = ${total} mg/day`,
      `${total} mg / ${water} L = ${conc} mg/L`,
      `${total} mg / ${potency} mg/g = ${productG} g product/day`,
    ],
    ["Assumes all birds drink the stated water volume; check actual intake."],
  );
}

export function withdrawal_end(a: { last_treatment: Date; withdrawal_hours: Num }): CalcResult {
  const h = dec(a.withdrawal_hours, "Withdrawal period");
  if (h.lt(0)) throw new CalcError("Withdrawal period cannot be negative.");
  const end = new Date(a.last_treatment.getTime() + h.mul(3600_000).toNumber());
  const r = result("end = last treatment + withdrawal period", { withdrawal_hours: h }, [
    `${a.last_treatment.toISOString()} + ${h} h = ${end.toISOString()}`,
  ]);
  r.eligible_from = end;
  return r;
}

/** Registry used by the shared-vector tests and generic calculator UI. */
export const ENGINE = {
  percent_to_mg_per_ml,
  mg_to_ml,
  ml_to_mg,
  dose_calc,
  dilution,
  dehydration_deficit,
  daily_fluid_need,
  infusion_rate,
  drip_rate,
  cri_rate,
  drinking_water_dose,
} as const;
