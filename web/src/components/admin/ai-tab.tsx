"use client";

import { useEffect, useState } from "react";
import { Button, Field, Skeleton, TextInput } from "@/components/ui/forms";
import { Modal } from "@/components/ui/modal";
import { Alert, DataTable, td, th } from "@/components/ui/primitives";
import { apiFetch, apiSend } from "@/lib/client-api";
import { CrudSection, type FieldDef } from "./crud-section";
import { ModelPicker } from "./model-picker";
import { fmt, useList } from "./tabs";

interface Provider extends Record<string, unknown> {
  id: number;
  kind: string;
  enabled: boolean;
  base_url: string;
  key_present: boolean;
  key_source: string;
  last_test_ok: boolean | null;
  last_test_message: string;
  last_test_at: string | null;
  spend_this_month_usd: string;
  monthly_budget_usd: string;
  default_model: string;
}
interface Route extends Record<string, unknown> {
  id: number;
  task: string;
  provider: number;
  model: string;
  enabled: boolean;
}
interface Usage {
  note: string;
  month_calls: number;
  month_failed: number;
  month_cost_usd: string;
  by_task: { task: string; model: string; calls: number; cost_usd: string; tokens: number }[];
  recent: { at: string; task: string; model: string; ok: boolean; error: string }[];
}

/** Seen in an AgentRouter token's model list; its console is the source of truth. */
const AGENTROUTER_MODELS = [
  "deepseek-v3.2",
  "glm-4.6",
  "gpt-6-astra",
  "gpt-6.1-sol",
  "gpt-5.6-sol",
];

/** Connection defaults filled in when a provider is picked. The env name is only a fallback:
 * a key entered in the admin panel wins. No model is pre-selected; names come from the provider. */
const PROVIDER_PRESETS: Record<string, { base_url: string; api_key_env: string }> = {
  openai: { base_url: "https://api.openai.com/v1", api_key_env: "OPENAI_API_KEY" },
  openrouter: { base_url: "https://openrouter.ai/api/v1", api_key_env: "OPENROUTER_API_KEY" },
  agentrouter: { base_url: "https://agentrouter.org/v1", api_key_env: "AGENTROUTER_API_KEY" },
};

function presetFor(name: string, value: unknown) {
  if (name !== "kind") return undefined;
  const p = PROVIDER_PRESETS[String(value)];
  return p ? { ...p, default_model: "" } : undefined;
}

function providerFields(modelsFor: (kind: unknown) => string[]): FieldDef[] {
  return PROVIDER_FIELDS.map((f) =>
    f.name === "default_model"
      ? { ...f, type: "model", suggestionsFor: (form) => modelsFor(form.kind) }
      : f,
  );
}

const PROVIDER_FIELDS: FieldDef[] = [
  {
    name: "kind",
    label: "Provider",
    type: "select",
    createOnly: true,
    options: [
      ["openai", "OpenAI API"],
      ["openrouter", "OpenRouter"],
      ["agentrouter", "AgentRouter (free coding-tool service; see warning above)"],
    ],
  },
  {
    name: "base_url",
    label: "Base URL (https)",
    type: "url",
    hint: "Filled in automatically when you pick a provider; change it only for a custom gateway.",
  },
  {
    name: "api_key_env",
    label: "Key reference (optional)",
    hint: "Name of a server environment variable, never the key itself. A key entered with the row action API key and model takes priority.",
  },
  { name: "default_model", label: "Preferred model" },
  { name: "monthly_budget_usd", label: "Monthly budget (USD, 0 = off)", type: "number" },
  { name: "timeout_seconds", label: "Timeout (seconds)", type: "number" },
  { name: "rate_limit_per_minute", label: "Rate limit (calls/minute)", type: "number" },
  { name: "enabled", label: "Enabled", type: "checkbox" },
];

const TASKS = [
  ["tagging", "Tagging / deduplication hints"],
  ["extraction", "Structured extraction"],
  ["drafting", "Editorial drafting"],
  ["summarising", "Summarising"],
  ["translation", "Translation"],
  ["triage", "Report / question triage"],
  ["suggestions", "Topic suggestions"],
] as const;

/** Enter/replace/remove a provider's key (write-only) and pick its model from the live list. */
function KeyDialog({
  provider,
  onClose,
  onChanged,
  onModels,
}: {
  provider: Provider;
  onClose: () => void;
  onChanged: () => void;
  onModels: (m: string[]) => void;
}) {
  const [key, setKey] = useState("");
  const [models, setModels] = useState<string[] | null>(null);
  const [model, setModel] = useState(provider.default_model);
  const [msg, setMsg] = useState<{ tone: "info" | "danger"; text: string } | null>(null);
  const [busy, setBusy] = useState("");

  async function run(name: string, fn: () => Promise<string | void>) {
    setBusy(name);
    setMsg(null);
    try {
      const text = await fn();
      if (text) setMsg({ tone: "info", text });
    } catch (e) {
      setMsg({ tone: "danger", text: e instanceof Error ? e.message : "Something went wrong." });
    } finally {
      setBusy("");
    }
  }
  const load = () =>
    run("models", async () => {
      const res = await apiFetch<{ ok: boolean; models: string[]; detail: string }>(
        `/staff/ai/providers/${provider.id}/models/`,
      );
      if (!res?.ok) return res?.detail || "Could not load models.";
      setModels(res.models);
      onModels(res.models);
      return `${res.models.length} models available.`;
    });
  const query = models ?? [];

  return (
    <Modal open title={`${provider.kind}: API key and model`} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-xs text-muted">
          {provider.key_present
            ? `A key is set (${provider.key_source}). For safety it is never shown again.`
            : "No key is set yet."}{" "}
          Keys are stored encrypted on the server and can be replaced or removed at any time.
        </p>
        {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
        <Field id="ai-key" label={provider.key_present ? "Replace key" : "API key"}>
          <TextInput
            id="ai-key"
            type="password"
            autoComplete="off"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="Paste the key from the provider"
          />
        </Field>
        <div className="flex flex-wrap gap-2">
          <Button
            loading={busy === "save"}
            disabled={!key.trim()}
            onClick={() =>
              run("save", async () => {
                await apiSend("PUT", `/staff/ai/providers/${provider.id}/key/`, {
                  api_key: key.trim(),
                });
                setKey("");
                onChanged();
                // Load this provider's models straight away so the list is ready to search.
                try {
                  const res = await apiFetch<{ ok: boolean; models: string[] }>(
                    `/staff/ai/providers/${provider.id}/models/`,
                  );
                  if (res?.ok) {
                    setModels(res.models);
                    onModels(res.models);
                    return `Key saved. ${res.models.length} models loaded; search and pick one.`;
                  }
                } catch {
                  /* fall through to the manual button */
                }
                return "Key saved. Use Load models from provider to see its models.";
              })
            }
          >
            Save key
          </Button>
          {provider.key_present && provider.key_source === "admin panel" && (
            <Button
              variant="secondary"
              loading={busy === "del"}
              onClick={() =>
                run("del", async () => {
                  await apiSend("DELETE", `/staff/ai/providers/${provider.id}/key/`);
                  onChanged();
                  return "Key removed.";
                })
              }
            >
              Remove key
            </Button>
          )}
        </div>
        <hr className="border-border" />
        <Button variant="secondary" loading={busy === "models"} onClick={load}>
          Load models from provider
        </Button>
        {models && (
          <Field id="ai-model" label="Model">
            <ModelPicker id="ai-model" value={model} onChange={setModel} models={query} />
          </Field>
        )}
        {models && (
          <Button
            disabled={!model}
            loading={busy === "use"}
            onClick={() =>
              run("use", async () => {
                await apiSend("PATCH", `/staff/ai/providers/${provider.id}/`, {
                  default_model: model,
                });
                onChanged();
                return `Preferred model set to ${model}.`;
              })
            }
          >
            Use this model
          </Button>
        )}
      </div>
    </Modal>
  );
}

export function AiTab() {
  const providers = useList<Provider>("/staff/ai/providers/");
  const [usage, setUsage] = useState<Usage | null | undefined>(undefined);
  useEffect(() => {
    apiFetch<Usage>("/staff/ai/usage/")
      .then((u) => setUsage(u ?? null))
      .catch(() => setUsage(null));
  }, []);
  // Models per provider kind, fetched live from each provider (AgentRouter also has a built-in list).
  const [fetched, setFetched] = useState<Record<string, string[]>>({});
  const addModels = (kind: string, m: string[]) =>
    setFetched((f) => ({ ...f, [kind]: [...new Set(m)].sort() }));
  const modelsFor = (kind: unknown): string[] => {
    const k = String(kind ?? "");
    return [...new Set([...(k === "agentrouter" ? AGENTROUTER_MODELS : []), ...(fetched[k] ?? [])])].sort();
  };
  const kindOf = (providerId: unknown) =>
    (providers.rows ?? []).find((p) => String(p.id) === String(providerId))?.kind;
  const [tick, setTick] = useState(0);
  const [keyFor, setKeyFor] = useState<Provider | null>(null);
  const provOptions: [string, string][] = (providers.rows ?? []).flatMap((p) => [
    [String(p.id), p.kind] as [string, string],
  ]);

  // Load each keyed provider's model list once so searching is instant.
  const rowsKey = (providers.rows ?? []).map((p) => `${p.id}:${p.key_present}`).join(",");
  useEffect(() => {
    for (const p of providers.rows ?? []) {
      if (!p.key_present) continue;
      apiFetch<{ ok: boolean; models: string[] }>(`/staff/ai/providers/${p.id}/models/`)
        .then((res) => {
          if (res?.ok) addModels(p.kind, res.models);
        })
        .catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowsKey]);

  return (
    <div className="space-y-8">
      <Alert tone="info" title="AI is optional and server-side">
        Keys are read from the server environment and are never shown here. AI only assists: drafts
        and suggestions stay unpublished, and dosages, treatments and regulatory claims always go to
        a qualified reviewer. Spend figures are estimates from token counts, not provider invoices.
      </Alert>
      <Alert tone="warn" title="AgentRouter: check its terms before using it here">
        As we read agentrouter.org/docs, it is a free service for developer coding tools and its
        terms restrict batch or synthetic content, bulk marketing/SEO text and general single-turn
        Q&A, with quotas and suspension at its discretion. VetRef&apos;s server-side tasks may fall
        under those limits, so prefer OpenAI or OpenRouter for production unless AgentRouter
        confirms in writing that this use is allowed.
      </Alert>

      <section className="space-y-2" aria-label="Providers">
        <h3 className="font-semibold">Providers</h3>
        <CrudSection<Provider>
          key={tick}
          path="/staff/ai/providers"
          caption="AI providers"
          empty="No provider configured. AI features stay off until you add one."
          newLabel="Add a provider"
          defaults={{
            kind: "openai",
            ...PROVIDER_PRESETS.openai,
            monthly_budget_usd: 0,
            timeout_seconds: 20,
            rate_limit_per_minute: 30,
          }}
          onFieldChange={presetFor}
          fields={providerFields(modelsFor)}
          columns={[
            { header: "Provider", render: (r) => `${r.kind}${r.enabled ? "" : " (off)"}` },
            {
              header: "Key / connection",
              render: (r) => (
                <>
                  {r.key_present ? "Key set" : "No key set"}
                  {r.last_test_at && (
                    <p className="text-xs text-muted">
                      {r.last_test_ok ? "Connected" : `Failed: ${r.last_test_message}`} ·{" "}
                      {fmt(r.last_test_at)}
                    </p>
                  )}
                </>
              ),
            },
            {
              header: "Spend (est.)",
              render: (r) => `$${r.spend_this_month_usd} of $${r.monthly_budget_usd}`,
            },
          ]}
          actions={[
            {
              label: "API key and model",
              run: async (r) => {
                setKeyFor(r);
              },
            },
            {
              label: "List models",
              run: async (r) => {
                const res = await apiFetch<{ ok: boolean; models: string[]; detail: string }>(
                  `/staff/ai/providers/${r.id}/models/`,
                );
                if (!res?.ok) return res?.detail || "Could not load models.";
                addModels(r.kind, res.models);
                return `${res.models.length} ${r.kind} models loaded; search them when choosing a model.`;
              },
            },
            {
              label: "Test connection",
              run: async (r) => {
                await apiSend("POST", `/staff/ai/providers/${r.id}/test/`, {});
              },
            },
          ]}
        />
      </section>

      {keyFor && (
        <KeyDialog
          provider={keyFor}
          onClose={() => setKeyFor(null)}
          onChanged={() => {
            providers.reload();
            setTick((t) => t + 1);
          }}
          onModels={(m) => addModels(keyFor.kind, m)}
        />
      )}

      <section className="space-y-2" aria-label="Task routing">
        <h3 className="font-semibold">Task routing</h3>
        <p className="text-xs text-muted">
          Use low-cost models for tagging, stronger ones for extraction and drafting. Calculations,
          price comparisons and permissions are always plain code, never AI.
        </p>
        <CrudSection<Route>
          path="/staff/ai/routes"
          caption="Task routing"
          empty="No task routes yet."
          newLabel="Route a task"
          dynamicOptions={{
            provider: provOptions,
            fallback_provider: [["", "No fallback"], ...provOptions],
          }}
          defaults={{ max_tokens: 800, enabled: true, fallback_provider: "" }}
          fields={[
            { name: "task", label: "Task", type: "select", options: TASKS, createOnly: true },
            { name: "provider", label: "Provider", type: "select" },
            {
              name: "model",
              label: "Model",
              type: "model",
              suggestionsFor: (form) => modelsFor(kindOf(form.provider)),
            },
            { name: "fallback_provider", label: "Fallback provider", type: "select" },
            {
              name: "fallback_model",
              label: "Fallback model",
              type: "model",
              suggestionsFor: (form) => modelsFor(kindOf(form.fallback_provider)),
            },
            { name: "max_tokens", label: "Max tokens", type: "number" },
            { name: "enabled", label: "Enabled", type: "checkbox" },
          ]}
          columns={[
            { header: "Task", render: (r) => r.task },
            {
              header: "Provider / model",
              render: (r) =>
                `${provOptions.find(([id]) => id === String(r.provider))?.[1] ?? r.provider} / ${r.model}`,
            },
            { header: "On", render: (r) => (r.enabled ? "Yes" : "No") },
          ]}
        />
      </section>

      <section className="space-y-2" aria-label="Usage">
        <h3 className="font-semibold">Usage this month</h3>
        {usage === undefined ? (
          <Skeleton className="h-16 w-full" />
        ) : usage === null ? (
          <Alert tone="danger">Could not load usage.</Alert>
        ) : usage.month_calls === 0 ? (
          <p className="text-sm text-muted">No AI calls yet.</p>
        ) : (
          <>
            <p className="text-sm">
              {usage.month_calls} calls, {usage.month_failed} failed, about ${usage.month_cost_usd}{" "}
              (estimate). {usage.note}
            </p>
            <DataTable caption="Usage by task">
              <thead>
                <tr>
                  <th className={th}>Task</th>
                  <th className={th}>Model</th>
                  <th className={th}>Calls</th>
                  <th className={th}>Tokens</th>
                  <th className={th}>Est. cost</th>
                </tr>
              </thead>
              <tbody>
                {usage.by_task.map((u) => (
                  <tr key={`${u.task}-${u.model}`}>
                    <td className={td}>{u.task}</td>
                    <td className={td}>{u.model}</td>
                    <td className={td}>{u.calls}</td>
                    <td className={td}>{u.tokens}</td>
                    <td className={td}>${u.cost_usd}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </>
        )}
      </section>
    </div>
  );
}
