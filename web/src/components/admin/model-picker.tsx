"use client";

import { useState } from "react";
import { Select, TextInput } from "@/components/ui/forms";

/**
 * Model chooser for one provider: a dropdown of that provider's models, with an optional filter
 * box above it for long lists. Only when no list is available does it fall back to typing a name.
 */
export function ModelPicker({
  id,
  value,
  onChange,
  models,
  emptyHint = "No models loaded yet. Save the key (models load automatically), or type a name.",
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  models: readonly string[];
  emptyHint?: string;
}) {
  const [q, setQ] = useState("");

  if (models.length === 0) {
    return (
      <div className="space-y-1">
        <TextInput id={id} value={value} onChange={(e) => onChange(e.target.value)} />
        <p className="text-xs text-muted">{emptyHint}</p>
      </div>
    );
  }

  const needle = q.trim().toLowerCase();
  const filtered = needle ? models.filter((m) => m.toLowerCase().includes(needle)) : [...models];
  // Keep the current choice selectable even when the filter hides it.
  const options = value && !filtered.includes(value) ? [value, ...filtered] : filtered;

  return (
    <div className="space-y-2">
      {models.length > 12 && (
        <TextInput
          id={`${id}-search`}
          type="search"
          aria-label="Filter this provider's models"
          placeholder={`Filter ${models.length} models…`}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      )}
      <Select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Choose a model</option>
        {options.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </Select>
      {needle && (
        <p className="text-xs text-muted">
          {filtered.length} of {models.length} match.
        </p>
      )}
    </div>
  );
}
