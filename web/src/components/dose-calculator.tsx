"use client";

import { useMemo, useState } from "react";
import {
  CalcError,
  dose_calc,
  percent_to_mg_per_ml,
  roundDisplay,
  type CalcResult,
} from "@/lib/calc/engine";
import { Alert } from "@/components/ui/primitives";

interface Props {
  presetDose?: string;
  presetDoseMax?: string;
  presetLabel?: string;
}

const input = "h-11 w-full rounded-md border border-border bg-surface px-3 text-base";

export function DoseCalculator({ presetDose = "", presetDoseMax = "", presetLabel = "" }: Props) {
  const [weight, setWeight] = useState("");
  const [unit, setUnit] = useState<"kg" | "lb">("kg");
  const [dose, setDose] = useState(presetDose);
  const [concMode, setConcMode] = useState<"mgml" | "percent">("mgml");
  const [conc, setConc] = useState("");
  const [maxDose, setMaxDose] = useState("");

  const outcome = useMemo(() => {
    if (!weight || !dose || !conc) return { kind: "idle" as const };
    try {
      const mgPerMl =
        concMode === "percent"
          ? percent_to_mg_per_ml({ percent: conc }).values.mg_per_ml.toString()
          : conc;
      const r = dose_calc({
        weight,
        weight_unit: unit,
        dose_mg_per_kg: dose,
        concentration_mg_per_ml: mgPerMl,
        max_dose_mg: maxDose || null,
      });
      return { kind: "ok" as const, r, conc: mgPerMl };
    } catch (e) {
      if (e instanceof CalcError) return { kind: "error" as const, message: e.message };
      throw e;
    }
  }, [weight, unit, dose, concMode, conc, maxDose]);

  return (
    <div className="space-y-4">
      {presetLabel && (
        <Alert tone="info" title="Dose prefilled from a link">
          {presetLabel}: {presetDose}
          {presetDoseMax && presetDoseMax !== presetDose ? `–${presetDoseMax}` : ""} mg/kg. Confirm
          against the source and the product label.
        </Alert>
      )}
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => e.preventDefault()} noValidate>
        <div>
          <label htmlFor="w" className="text-sm font-medium">
            Body weight
          </label>
          <div className="flex gap-2">
            <input
              id="w"
              inputMode="decimal"
              className={input}
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
            />
            <select
              aria-label="Weight unit"
              className="h-11 rounded-md border border-border bg-surface px-2"
              value={unit}
              onChange={(e) => setUnit(e.target.value as "kg" | "lb")}
            >
              <option value="kg">kg</option>
              <option value="lb">lb</option>
            </select>
          </div>
        </div>
        <div>
          <label htmlFor="d" className="text-sm font-medium">
            Dose rate (mg/kg)
          </label>
          <input
            id="d"
            inputMode="decimal"
            className={input}
            value={dose}
            onChange={(e) => setDose(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="c" className="text-sm font-medium">
            Product concentration
          </label>
          <div className="flex gap-2">
            <input
              id="c"
              inputMode="decimal"
              className={input}
              value={conc}
              onChange={(e) => setConc(e.target.value)}
            />
            <select
              aria-label="Concentration unit"
              className="h-11 rounded-md border border-border bg-surface px-2"
              value={concMode}
              onChange={(e) => setConcMode(e.target.value as "mgml" | "percent")}
            >
              <option value="mgml">mg/mL</option>
              <option value="percent">% (w/v)</option>
            </select>
          </div>
          <p className="mt-1 text-xs text-muted">Read from the product label.</p>
        </div>
        <div>
          <label htmlFor="m" className="text-sm font-medium">
            Maximum dose in mg (optional)
          </label>
          <input
            id="m"
            inputMode="decimal"
            className={input}
            value={maxDose}
            onChange={(e) => setMaxDose(e.target.value)}
          />
        </div>
      </form>

      <div aria-live="polite" className="space-y-3">
        {outcome.kind === "error" && <Alert tone="danger">{outcome.message}</Alert>}
        {outcome.kind === "ok" && <Result r={outcome.r} />}
        {outcome.kind === "idle" && (
          <p className="text-sm text-muted">
            Enter weight, dose rate and concentration to calculate.
          </p>
        )}
      </div>
    </div>
  );
}

function Result({ r }: { r: CalcResult }) {
  return (
    <div className="space-y-3 rounded-md border border-border bg-surface p-4">
      {r.warnings.map((w) => (
        <Alert key={w} tone="warn" title="Check before administering">
          {w}
        </Alert>
      ))}
      <dl className="grid grid-cols-2 gap-3">
        <div>
          <dt className="text-sm text-muted">Total active ingredient</dt>
          <dd className="text-2xl font-semibold">{roundDisplay(r.values.total_mg, 2)} mg</dd>
        </div>
        <div>
          <dt className="text-sm text-muted">Volume to administer</dt>
          <dd className="text-2xl font-semibold">{roundDisplay(r.values.volume_ml, 2)} mL</dd>
        </div>
      </dl>
      <details className="text-sm">
        <summary className="cursor-pointer font-medium">Formula and steps</summary>
        <p className="mt-2 font-mono text-xs">{r.formula}</p>
        <ol className="mt-2 list-decimal space-y-1 pl-5">
          {r.steps.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
        <p className="mt-2 text-muted">
          Displayed values are rounded; the calculation uses exact decimals.
        </p>
      </details>
    </div>
  );
}
