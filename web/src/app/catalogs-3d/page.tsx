import type { Metadata } from "next";
import Link from "next/link";
import { CatalogLeadForm } from "@/components/catalog-lead-form";
import { ModelViewer } from "@/components/model-viewer";
import { Breadcrumbs, EmptyState } from "@/components/ui/primitives";
import { apiGet } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "3D catalogs",
  description: "Interactive 3D product catalogs from approved veterinary suppliers.",
  alternates: { canonical: "/catalogs-3d" },
};

interface Catalog {
  id: number;
  title: string;
  description: string;
  collection: string;
  supplier: string;
  product: string | null;
  fallback_image: string;
  asset_url: string | null;
}
interface Plans {
  results: {
    id: number;
    name: string;
    kind: string;
    amount: string;
    currency: string;
    description: string;
  }[];
  note: string;
}

export default async function Page() {
  const [{ results }, plans] = await Promise.all([
    apiGet<{ results: Catalog[] }>("/catalogs-3d/", 60),
    apiGet<Plans>("/catalog-plans/", 60),
  ]);
  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "3D catalogs" }]} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">3D catalogs</h1>
        <Link href="/catalogs-3d/supplier" className="text-sm text-primary underline">
          Supplier area
        </Link>
      </div>
      {results.length === 0 ? (
        <EmptyState title="No approved 3D catalogs yet.">
          Suppliers can apply in the supplier area. Every model is reviewed before it is shown.
        </EmptyState>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {results.map((c) => (
            <li key={c.id} className="card space-y-2 p-4">
              {c.asset_url ? (
                <ModelViewer
                  src={c.asset_url}
                  alt={c.title}
                  fallbackImage={c.fallback_image || undefined}
                />
              ) : c.fallback_image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={c.fallback_image} alt={c.title} className="w-full rounded-lg" />
              ) : null}
              <h2 className="font-semibold">{c.title}</h2>
              <p className="text-xs text-muted">
                {c.supplier}
                {c.collection && ` · ${c.collection}`}
              </p>
              {c.description && <p className="text-sm">{c.description}</p>}
              {c.product && (
                <Link href={`/products/${c.product}`} className="text-sm text-primary underline">
                  View product record
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
      <section aria-labelledby="plans" className="space-y-3">
        <h2 id="plans" className="text-xl font-semibold">
          Plans and enquiries
        </h2>
        {plans.results.length > 0 && (
          <ul className="grid gap-3 sm:grid-cols-3">
            {plans.results.map((p) => (
              <li key={p.id} className="card p-3 text-sm">
                <p className="font-semibold">{p.name}</p>
                <p>
                  {p.currency} {p.amount}{" "}
                  <span className="text-muted">({p.kind.replaceAll("_", " ")})</span>
                </p>
                {p.description && <p className="text-muted">{p.description}</p>}
              </li>
            ))}
          </ul>
        )}
        <p className="text-sm text-muted">{plans.note}</p>
        <CatalogLeadForm plans={plans.results.map((p) => ({ id: p.id, name: p.name }))} />
      </section>
    </div>
  );
}
