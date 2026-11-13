"use client";

import { useState, type FormEvent } from "react";
import { Button, Field, Select, TextInput } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { ClientApiError, apiSend } from "@/lib/client-api";

export function CatalogLeadForm({ plans }: { plans: { id: number; name: string }[] }) {
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.currentTarget).entries());
    setState("busy");
    setError(null);
    try {
      await apiSend("POST", "/catalog-leads/", {
        ...body,
        plan: body.plan ? Number(body.plan) : null,
      });
      setState("done");
    } catch (err) {
      setError(err instanceof ClientApiError ? err.message : "Could not send your enquiry.");
      setState("idle");
    }
  }

  if (state === "done") return <Alert tone="info">Thank you. We will contact you.</Alert>;
  return (
    <form onSubmit={submit} className="card max-w-lg space-y-3 p-4">
      <h3 className="font-semibold">Send an enquiry</h3>
      {error && <Alert tone="danger">{error}</Alert>}
      <Field id="lead-name" label="Name">
        <TextInput id="lead-name" name="name" required maxLength={120} />
      </Field>
      <Field id="lead-email" label="Email">
        <TextInput id="lead-email" name="email" type="email" required />
      </Field>
      <Field id="lead-company" label="Company">
        <TextInput id="lead-company" name="company" maxLength={160} />
      </Field>
      {plans.length > 0 && (
        <Field id="lead-plan" label="Plan of interest">
          <Select id="lead-plan" name="plan" defaultValue="">
            <option value="">Not sure yet</option>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </Field>
      )}
      <Field id="lead-msg" label="Message">
        <TextInput id="lead-msg" name="message" maxLength={1000} />
      </Field>
      <Button type="submit" loading={state === "busy"}>
        Send
      </Button>
    </form>
  );
}
