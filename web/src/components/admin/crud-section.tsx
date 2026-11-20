"use client";

import { useState, type ReactNode } from "react";
import { Button, Field, Select, TextInput } from "@/components/ui/forms";
import { Modal } from "@/components/ui/modal";
import { Alert, DataTable, td, th } from "@/components/ui/primitives";
import { apiSend } from "@/lib/client-api";
import { ModelPicker } from "./model-picker";
import { ListShell, errText, useList } from "./tabs";

export interface FieldDef {
  name: string;
  label: string;
  type?: "text" | "textarea" | "number" | "select" | "checkbox" | "url" | "model";
  options?: readonly (readonly [string, string])[];
  hint?: string;
  /** Suggested values for a text field (free text is still allowed). */
  suggestions?: readonly string[];
  /** Suggestions that depend on the other form values (e.g. the chosen provider). */
  suggestionsFor?: (form: Record<string, unknown>) => readonly string[];
  /** Only editable when creating. */
  createOnly?: boolean;
}
export interface Column<R> {
  header: string;
  render: (row: R) => ReactNode;
}
export interface RowAction<R> {
  label: string;
  /** Posts to `${path}/${id}/${post}/`. */
  post?: string;
  /** May return a short message to show to the admin. */
  run?: (row: R) => Promise<unknown>;
  show?: (row: R) => boolean;
  danger?: boolean;
  confirm?: string;
}

type Row = { id: number } & Record<string, unknown>;

/** One reusable list + create/edit modal + row actions for admin resources backed by the API. */
export function CrudSection<R extends Row>({
  path,
  fields,
  columns,
  actions = [],
  newLabel,
  empty,
  caption,
  canEdit = true,
  canCreate = true,
  defaults = {},
  intro,
  dynamicOptions = {},
  onFieldChange,
}: {
  path: string;
  fields: FieldDef[];
  columns: Column<R>[];
  actions?: RowAction<R>[];
  newLabel?: string;
  empty: string;
  caption: string;
  canEdit?: boolean;
  canCreate?: boolean;
  defaults?: Record<string, unknown>;
  intro?: ReactNode;
  /** Options for select fields that depend on other data (e.g. a list of providers). */
  dynamicOptions?: Record<string, readonly (readonly [string, string])[]>;
  /** Extra values to fill in when a field changes (e.g. provider presets). Only on create. */
  onFieldChange?: (name: string, value: unknown) => Record<string, unknown> | undefined;
}) {
  const list = useList<R>(`${path}/`);
  const [editing, setEditing] = useState<R | "new" | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function open(row: R | "new") {
    setError(null);
    setForm(row === "new" ? { ...defaults } : { ...row });
    setEditing(row);
  }

  async function save() {
    if (!editing) return;
    setBusy("save");
    setError(null);
    try {
      if (editing === "new") await apiSend("POST", `${path}/`, form);
      else {
        const body: Record<string, unknown> = {};
        for (const f of fields) if (!f.createOnly) body[f.name] = form[f.name];
        await apiSend("PATCH", `${path}/${editing.id}/`, body);
      }
      setEditing(null);
      list.reload();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  async function act(a: RowAction<R>, row: R) {
    if (a.confirm && !window.confirm(a.confirm)) return;
    setBusy(`${a.label}-${row.id}`);
    setError(null);
    setNotice(null);
    try {
      if (a.run) {
        const out = await a.run(row);
        if (typeof out === "string") setNotice(out);
      } else if (a.post) await apiSend("POST", `${path}/${row.id}/${a.post}/`, {});
      list.reload();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3">
      {intro && <div className="text-sm text-muted">{intro}</div>}
      {error && !editing && <Alert tone="danger">{error}</Alert>}
      {notice && <Alert tone="info">{notice}</Alert>}
      {canCreate && newLabel && (
        <Button onClick={() => open("new")} variant="secondary">
          {newLabel}
        </Button>
      )}
      <ListShell list={list} empty={empty}>
        {(rows) => (
          <DataTable caption={caption}>
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c.header} className={th}>
                    {c.header}
                  </th>
                ))}
                <th className={th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  {columns.map((c) => (
                    <td key={c.header} className={`${td} break-words`}>
                      {c.render(r)}
                    </td>
                  ))}
                  <td className={`${td} space-x-3`}>
                    {canEdit && (
                      <button className="text-primary underline" onClick={() => open(r)}>
                        Edit
                      </button>
                    )}
                    {actions
                      .filter((a) => !a.show || a.show(r))
                      .map((a) => (
                        <button
                          key={a.label}
                          disabled={busy === `${a.label}-${r.id}`}
                          className={`underline disabled:opacity-50 ${a.danger ? "text-danger" : "text-primary"}`}
                          onClick={() => act(a, r)}
                        >
                          {a.label}
                        </button>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}
      </ListShell>

      <Modal
        open={!!editing}
        title={editing === "new" ? (newLabel ?? "New") : "Edit"}
        onClose={() => setEditing(null)}
      >
        <div className="max-h-[65vh] space-y-3 overflow-y-auto pr-1">
          {error && <Alert tone="danger">{error}</Alert>}
          {fields
            .filter((f) => editing === "new" || !f.createOnly)
            .map((f) => {
              const id = `f-${f.name}`;
              const v = form[f.name];
              const set = (x: unknown) =>
                setForm((s) => ({
                  ...s,
                  [f.name]: x,
                  ...(editing === "new" ? onFieldChange?.(f.name, x) : undefined),
                }));
              const suggestions = f.suggestionsFor ? f.suggestionsFor(form) : f.suggestions;
              if (f.type === "checkbox")
                return (
                  <label key={f.name} className="flex min-h-11 items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={!!v}
                      onChange={(e) => set(e.target.checked)}
                      className="size-4"
                    />
                    {f.label}
                    {f.hint && <span className="text-xs text-muted">({f.hint})</span>}
                  </label>
                );
              return (
                <Field key={f.name} id={id} label={f.label} hint={f.hint}>
                  {f.type === "select" ? (
                    <Select id={id} value={String(v ?? "")} onChange={(e) => set(e.target.value)}>
                      {(f.options ?? dynamicOptions[f.name])?.map(([val, lab]) => (
                        <option key={val} value={val}>
                          {lab}
                        </option>
                      ))}
                    </Select>
                  ) : f.type === "model" ? (
                    <ModelPicker
                      id={id}
                      value={String(v ?? "")}
                      onChange={set}
                      models={suggestions ?? []}
                    />
                  ) : f.type === "textarea" ? (
                    <textarea
                      id={id}
                      value={String(v ?? "")}
                      rows={4}
                      onChange={(e) => set(e.target.value)}
                      className="neo-inset w-full rounded-lg border border-border px-3 py-2 text-sm"
                    />
                  ) : (
                    <>
                      <TextInput
                        id={id}
                        type={f.type === "number" ? "number" : f.type === "url" ? "url" : "text"}
                        value={String(v ?? "")}
                        list={suggestions ? `${id}-list` : undefined}
                        onChange={(e) => set(e.target.value)}
                      />
                      {suggestions && (
                        <datalist id={`${id}-list`}>
                          {suggestions.map((m) => (
                            <option key={m} value={m} />
                          ))}
                        </datalist>
                      )}
                    </>
                  )}
                </Field>
              );
            })}
        </div>
        <div className="mt-3 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setEditing(null)}>
            Cancel
          </Button>
          <Button loading={busy === "save"} onClick={save}>
            Save
          </Button>
        </div>
      </Modal>
    </div>
  );
}
