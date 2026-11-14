"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { Button, Field, TextInput } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { ClientApiError, apiFetch, apiSend } from "@/lib/client-api";
import { useUser } from "@/lib/use-user";

interface Me {
  supplier: { id: number; name: string; status: string } | null;
}
const MAX = 3 * 1024 * 1024;

function toBase64(buf: ArrayBuffer): string {
  let s = "";
  const b = new Uint8Array(buf);
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode(...b.subarray(i, i + 0x8000));
  return btoa(s);
}

export function SupplierArea() {
  const user = useUser();
  const [me, setMe] = useState<Me | null>(null);
  const [msg, setMsg] = useState<{ tone: "info" | "danger"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) apiFetch<Me>("/my/supplier/").then((m) => setMe(m ?? { supplier: null }));
  }, [user]);

  if (user === undefined) return null;
  if (!user)
    return (
      <Alert tone="info">
        <Link href="/login?next=/catalogs-3d/supplier" className="underline">
          Sign in
        </Link>{" "}
        to apply as a supplier.
      </Alert>
    );
  const fail = (e: unknown) =>
    setMsg({
      tone: "danger",
      text: e instanceof ClientApiError ? e.message : "Something went wrong.",
    });

  async function apply(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    try {
      setMe(
        await apiSend<Me>(
          "POST",
          "/my/supplier/",
          Object.fromEntries(new FormData(e.currentTarget)),
        ),
      );
      setMsg(null);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const file = f.get("file");
    if (!(file instanceof File) || !file.name.toLowerCase().endsWith(".glb"))
      return setMsg({ tone: "danger", text: "Choose a .glb file." });
    if (file.size > MAX) return setMsg({ tone: "danger", text: "The file is larger than 3 MB." });
    setBusy(true);
    try {
      await apiSend("POST", "/my/catalogs-3d/", {
        title: f.get("title"),
        description: f.get("description"),
        collection: f.get("collection"),
        price_amount: f.get("price_amount") || null,
        price_currency: f.get("price_currency"),
        rights_confirmed: f.get("rights") === "on",
        asset_base64: toBase64(await file.arrayBuffer()),
      });
      form.reset();
      setMsg({ tone: "info", text: "Uploaded. Staff review each model before it is shown." });
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
      {!me?.supplier ? (
        <form onSubmit={apply} className="card space-y-3 p-4">
          <h2 className="font-semibold">Apply as a supplier</h2>
          <Field id="s-name" label="Company name">
            <TextInput id="s-name" name="name" required maxLength={160} />
          </Field>
          <Field id="s-web" label="Website">
            <TextInput id="s-web" name="website" type="url" />
          </Field>
          <Field id="s-desc" label="About">
            <TextInput id="s-desc" name="description" maxLength={2000} />
          </Field>
          <Button type="submit" loading={busy}>
            Apply
          </Button>
        </form>
      ) : me.supplier.status !== "approved" ? (
        <Alert tone="info">
          {me.supplier.name}: your application is {me.supplier.status}. You can upload models once
          staff approve it.
        </Alert>
      ) : (
        <form onSubmit={upload} className="card space-y-3 p-4">
          <h2 className="font-semibold">Upload a model ({me.supplier.name})</h2>
          <p className="text-xs text-muted">
            Binary glTF (.glb) up to 3 MB, without compressed-mesh extensions. Every file is scanned
            for unsafe content before it is accepted, and staff review each model before it is
            public.
          </p>
          <Field id="c-title" label="Title">
            <TextInput id="c-title" name="title" required maxLength={160} />
          </Field>
          <Field id="c-collection" label="Collection">
            <TextInput id="c-collection" name="collection" maxLength={100} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="c-price" label="Price (optional)">
              <TextInput id="c-price" name="price_amount" type="number" min="0" step="0.01" />
            </Field>
            <Field id="c-ccy" label="Currency">
              <TextInput id="c-ccy" name="price_currency" maxLength={3} placeholder="USD" />
            </Field>
          </div>
          <Field id="c-desc" label="Description">
            <TextInput id="c-desc" name="description" maxLength={2000} />
          </Field>
          <Field id="c-file" label="Model file (.glb)">
            <input id="c-file" name="file" type="file" accept=".glb,model/gltf-binary" required />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="rights" required className="size-4" />I own this model or
            have the right to license it.
          </label>
          <Button type="submit" loading={busy}>
            Upload for review
          </Button>
        </form>
      )}
    </div>
  );
}
