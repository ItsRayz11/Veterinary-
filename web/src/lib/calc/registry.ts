import {
  cri_rate,
  daily_fluid_need,
  dehydration_deficit,
  dilution,
  drinking_water_dose,
  drip_rate,
  infusion_rate,
  withdrawal_end,
  type CalcResult,
} from "./engine";

/** Field kinds: plain number, body weight (value + unit), or a date/time. No field has a clinical default. */
export type FieldDef =
  | { name: string; label: string; kind: "number"; hint?: string }
  | { name: string; label: string; kind: "weight"; hint?: string }
  | { name: string; label: string; kind: "datetime"; hint?: string };

export interface OutputDef {
  key: string;
  label: string;
  unit: string;
  places?: number;
}

export interface CalcDef {
  slug: string;
  title: string;
  description: string;
  fields: FieldDef[];
  outputs: OutputDef[];
  /** Values are raw strings from the form (weight fields also provide `<name>_unit`). */
  run: (v: Record<string, string>) => CalcResult;
}

type WU = "kg" | "lb" | "g";
const wu = (v: Record<string, string>) => (v.weight_unit || "kg") as WU;

export const CALCULATORS: CalcDef[] = [
  {
    slug: "dilution",
    title: "Dilution",
    description: "How much stock solution and diluent make a target concentration (C1V1 = C2V2).",
    fields: [
      {
        name: "stock_conc",
        label: "Stock concentration",
        kind: "number",
        hint: "Any unit, same as target",
      },
      {
        name: "target_conc",
        label: "Target concentration",
        kind: "number",
        hint: "Same unit as stock",
      },
      { name: "final_volume_ml", label: "Final volume (mL)", kind: "number" },
    ],
    outputs: [
      { key: "stock_volume_ml", label: "Stock solution", unit: "mL" },
      { key: "diluent_ml", label: "Diluent", unit: "mL" },
    ],
    run: (v) =>
      dilution({
        stock_conc: v.stock_conc,
        target_conc: v.target_conc,
        final_volume_ml: v.final_volume_ml,
      }),
  },
  {
    slug: "dehydration-deficit",
    title: "Dehydration deficit",
    description: "Fluid deficit from body weight and estimated dehydration percentage.",
    fields: [
      { name: "weight", label: "Body weight", kind: "weight" },
      {
        name: "dehydration_percent",
        label: "Dehydration (%)",
        kind: "number",
        hint: "Clinical estimate, up to 30",
      },
    ],
    outputs: [{ key: "deficit_ml", label: "Fluid deficit", unit: "mL" }],
    run: (v) =>
      dehydration_deficit({
        weight: v.weight,
        weight_unit: wu(v),
        dehydration_percent: v.dehydration_percent,
      }),
  },
  {
    slug: "daily-fluid-need",
    title: "Daily fluid volume",
    description:
      "Volume per day and per hour for a fluid rate you supply. The rate is not built in; take it from your protocol or source.",
    fields: [
      { name: "weight", label: "Body weight", kind: "weight" },
      { name: "ml_per_kg_per_day", label: "Fluid rate (mL/kg/day)", kind: "number" },
    ],
    outputs: [
      { key: "ml_per_day", label: "Per day", unit: "mL" },
      { key: "ml_per_hour", label: "Per hour", unit: "mL/h" },
    ],
    run: (v) =>
      daily_fluid_need({
        weight: v.weight,
        weight_unit: wu(v),
        ml_per_kg_per_day: v.ml_per_kg_per_day,
      }),
  },
  {
    slug: "infusion-rate",
    title: "Infusion rate",
    description: "Pump rate in mL/h for a volume given over a set time.",
    fields: [
      { name: "volume_ml", label: "Volume (mL)", kind: "number" },
      { name: "hours", label: "Duration (hours)", kind: "number" },
    ],
    outputs: [{ key: "ml_per_hour", label: "Rate", unit: "mL/h" }],
    run: (v) => infusion_rate({ volume_ml: v.volume_ml, hours: v.hours }),
  },
  {
    slug: "drip-rate",
    title: "Drip rate",
    description: "Drops per minute for a gravity giving set.",
    fields: [
      { name: "volume_ml", label: "Volume (mL)", kind: "number" },
      { name: "hours", label: "Duration (hours)", kind: "number" },
      {
        name: "drops_per_ml",
        label: "Drop factor (drops/mL)",
        kind: "number",
        hint: "Printed on the giving set",
      },
    ],
    outputs: [
      { key: "drops_per_min", label: "Rate", unit: "drops/min" },
      { key: "seconds_per_drop", label: "One drop every", unit: "s" },
    ],
    run: (v) => drip_rate({ volume_ml: v.volume_ml, hours: v.hours, drops_per_ml: v.drops_per_ml }),
  },
  {
    slug: "cri",
    title: "CRI pump rate",
    description: "Constant-rate infusion pump rate for a mcg/kg/min dose.",
    fields: [
      { name: "weight", label: "Body weight", kind: "weight" },
      { name: "dose_mcg_per_kg_min", label: "Dose (mcg/kg/min)", kind: "number" },
      {
        name: "concentration_mg_per_ml",
        label: "Concentration (mg/mL)",
        kind: "number",
        hint: "Of the solution in the pump",
      },
    ],
    outputs: [
      { key: "ml_per_hour", label: "Pump rate", unit: "mL/h" },
      { key: "mcg_per_hour", label: "Drug delivered", unit: "mcg/h" },
    ],
    run: (v) =>
      cri_rate({
        weight: v.weight,
        weight_unit: wu(v),
        dose_mcg_per_kg_min: v.dose_mcg_per_kg_min,
        concentration_mg_per_ml: v.concentration_mg_per_ml,
      }),
  },
  {
    slug: "flock-water-dose",
    title: "Flock drinking-water dose",
    description:
      "Medication concentration and product quantity for a flock treated via drinking water.",
    fields: [
      { name: "birds", label: "Number of birds", kind: "number" },
      { name: "avg_weight_kg", label: "Average bird weight (kg)", kind: "number" },
      { name: "dose_mg_per_kg", label: "Dose (mg/kg body weight/day)", kind: "number" },
      { name: "water_litres_per_day", label: "Flock water intake (L/day)", kind: "number" },
      {
        name: "product_mg_per_g",
        label: "Product strength (mg active per g)",
        kind: "number",
        hint: "From the product label",
      },
    ],
    outputs: [
      { key: "total_mg_per_day", label: "Total active", unit: "mg/day" },
      { key: "mg_per_litre", label: "Concentration in water", unit: "mg/L" },
      { key: "product_g_per_day", label: "Product needed", unit: "g/day" },
    ],
    run: (v) =>
      drinking_water_dose({
        birds: v.birds,
        avg_weight_kg: v.avg_weight_kg,
        dose_mg_per_kg: v.dose_mg_per_kg,
        water_litres_per_day: v.water_litres_per_day,
        product_mg_per_g: v.product_mg_per_g,
      }),
  },
  {
    slug: "withdrawal-date",
    title: "Withdrawal end date",
    description:
      "Earliest date and time for products to enter the food chain. Enter the withdrawal period from the product label or a sourced record for your country.",
    fields: [
      { name: "last_treatment", label: "Last treatment", kind: "datetime" },
      {
        name: "withdrawal_hours",
        label: "Withdrawal period (hours)",
        kind: "number",
        hint: "Days x 24",
      },
    ],
    outputs: [{ key: "withdrawal_hours", label: "Withdrawal period", unit: "h", places: 0 }],
    run: (v) => {
      const when = new Date(v.last_treatment);
      if (Number.isNaN(when.getTime()))
        throw new Error("Last treatment must be a valid date and time.");
      return withdrawal_end({ last_treatment: when, withdrawal_hours: v.withdrawal_hours });
    },
  },
];

export const bySlug = (slug: string) => CALCULATORS.find((c) => c.slug === slug);
