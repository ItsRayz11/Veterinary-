"use client";

import { useMemo, useState } from "react";
import { Alert } from "@/components/ui/primitives";
import { Field, Select, TextInput } from "@/components/ui/forms";
import { CalcError, roundDisplay } from "@/lib/calc/engine";
import { bySlug } from "@/lib/calc/registry";

/** Generic UI over the pure TypeScript engine (identical results to the API via shared vectors). */
export function GenericCalculator({ slug }: { slug: string }) {
  const def = bySlug(slug)!;
  const [values, setValues] = useState<Record<string, string>>({});
  const set = (k: string, v: string) => setValues((s) => ({ ...s, [k]: v }));

  const outcome = useMemo(() => {
    if (def.fields.some((f) => !values[f.name]?.trim())) return { kind: "idle" as const };
    try {
      return { kind: "ok" as const, r: def.run(values) };
    } catch (e) {
      if (e instanceof CalcError || e instanceof Error)
        return { kind: "error" as const, message: e.message };
      throw e;
    }
  }, [def, values]);

  return (
    <div className="space-y-4">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => e.preventDefault()} noValidate>
        {def.fields.map((f) => (
          <Field key={f.name} id={f.name} label={f.label} hint={f.hint}>
            {f.kind === "weight" ? (
              <div className="flex gap-2">
                <TextInput
                  id={f.name}
                  inputMode="decimal"
                  value={values[f.name] ?? ""}
                  onChange={(e) => set(f.name, e.target.value)}
                />
                <Select
                  id={`${f.name}_unit`}
                  aria-label="Weight unit"
                  className="w-24"
                  value={values.weight_unit ?? "kg"}
                  onChange={(e) => set("weight_unit", e.target.value)}
                >
                  <option value="kg">kg</option>
                  <option value="lb">lb</option>
                  <option value="g">g</option>
                </Select>
              </div>
            ) : (
              <TextInput
                id={f.name}
                type={f.kind === "datetime" ? "datetime-local" : "text"}
                inputMode={f.kind === "number" ? "decimal" : undefined}
                value={values[f.name] ?? ""}
                onChange={(e) => set(f.name, e.target.value)}
              />
            )}
          </Field>
        ))}
      </form>

      <div aria-live="polite" className="space-y-3">
        {outcome.kind === "idle" && (
          <p className="text-sm text-muted">Fill in every field to calculate.</p>
        )}
        {outcome.kind === "error" && <Alert tone="danger">{outcome.message}</Alert>}
        {outcome.kind === "ok" && (
          <div className="space-y-3 rounded-md border border-border bg-surface p-4">
            {outcome.r.warnings.map((w) => (
              <Alert key={w} tone="warn" title="Check before administering">
                {w}
              </Alert>
            ))}
            <dl className="grid grid-cols-2 gap-3">
              {def.outputs.map((o) => (
                <div key={o.key}>
                  <dt className="text-sm text-muted">{o.label}</dt>
                  <dd className="text-2xl font-semibold">
                    {roundDisplay(outcome.r.values[o.key], o.places ?? 2)} {o.unit}
                  </dd>
                </div>
              ))}
              {outcome.r.eligible_from && (
                <div className="col-span-2">
                  <dt className="text-sm text-muted">Earliest release</dt>
                  <dd className="text-2xl font-semibold">
                    {outcome.r.eligible_from.toLocaleString()}
                  </dd>
                </div>
              )}
            </dl>
            <details className="text-sm">
              <summary className="cursor-pointer font-medium">Formula and steps</summary>
              <p className="mt-2 font-mono text-xs">{outcome.r.formula}</p>
              <ol className="mt-2 list-decimal space-y-1 pl-5">
                {outcome.r.steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
              <p className="mt-2 text-muted">
                Displayed values are rounded; the calculation uses exact decimals.
              </p>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
