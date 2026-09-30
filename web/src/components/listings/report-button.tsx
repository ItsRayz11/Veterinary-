"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, Field, TextInput } from "@/components/ui/forms";
import { ClientApiError, apiSend } from "@/lib/client-api";
import { useUser } from "@/lib/use-user";

export function ReportButton({ kind, id }: { kind: string; id: number }) {
  const user = useUser();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [note, setNote] = useState<string | null>(null);

  if (note)
    return (
      <p role="status" className="text-sm text-muted">
        {note}
      </p>
    );
  if (!open)
    return (
      <button
        type="button"
        className="text-sm text-primary underline"
        onClick={() => setOpen(true)}
      >
        Report this listing
      </button>
    );
  if (user === null)
    return (
      <p className="text-sm">
        <Link className="underline" href={`/login?next=/${kind}/${id}`}>
          Sign in
        </Link>{" "}
        to report a listing.
      </p>
    );
  return (
    <div className="space-y-2">
      <Field id="report" label="What is wrong? (scam, expired, wrong details)">
        <TextInput
          id="report"
          value={message}
          maxLength={300}
          onChange={(e) => setMessage(e.target.value)}
        />
      </Field>
      <Button
        disabled={!message.trim()}
        onClick={async () => {
          try {
            await apiSend("POST", `/listings/${kind}/${id}/report`, { message });
            setNote("Thanks. Moderators will look at it.");
          } catch (e) {
            setNote(
              e instanceof ClientApiError ? (e.fields.message ?? e.message) : "Could not send.",
            );
          }
        }}
      >
        Send report
      </Button>
    </div>
  );
}
