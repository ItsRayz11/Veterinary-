"use client";

import { useState } from "react";
import { TextInput } from "@/components/ui/forms";

/**
 * Model chooser for one provider: the chosen value stays free text (some gateways hide models),
 * with a search box and a scrollable list of that provider's models to pick from.
 */
export function ModelPicker({
  id,
  value,
  onChange,
  models,
  emptyHint = "No models loaded yet. Add the key and use List models, or type the name.",
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  models: readonly string[];
  emptyHint?: string;
}) {
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const shown = needle ? models.filter((m) => m.toLowerCase().includes(needle)) : models;

  return (
    <div className="space-y-2">
      <TextInput
        id={id}
        value={value}
        placeholder="Selected model (type a name or pick below)"
        onChange={(e) => onChange(e.target.value)}
      />
      {models.length === 0 ? (
        <p className="text-xs text-muted">{emptyHint}</p>
      ) : (
        <div className="space-y-1">
          <TextInput
            id={`${id}-search`}
            type="search"
            aria-label="Search this provider's models"
            placeholder={`Search ${models.length} models`}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <ul
            aria-label="Models"
            className="max-h-48 overflow-y-auto rounded-lg border border-border bg-surface"
          >
            {shown.length === 0 && <li className="px-3 py-2 text-xs text-muted">No match.</li>}
            {shown.map((m) => (
              <li key={m}>
                <button
                  type="button"
                  onClick={() => onChange(m)}
                  aria-pressed={m === value}
                  className={`block min-h-9 w-full break-all px-3 py-1.5 text-left text-sm hover:bg-surface-2 ${
                    m === value ? "font-semibold text-primary" : ""
                  }`}
                >
                  {m}
                </button>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">
            Showing {shown.length} of {models.length}.
          </p>
        </div>
      )}
    </div>
  );
}
