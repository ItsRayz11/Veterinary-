"use client";

import { apiSend } from "@/lib/client-api";
import { CrudSection } from "./crud-section";
import { fmt } from "./tabs";

interface Supplier extends Record<string, unknown> {
  id: number;
  name: string;
  owner: string;
  status: string;
}
interface Catalog extends Record<string, unknown> {
  id: number;
  title: string;
  supplier_name: string;
  status: string;
  asset_size: number;
  rights_confirmed: boolean;
  reject_reason: string;
}
interface Plan extends Record<string, unknown> {
  id: number;
  name: string;
  kind: string;
  amount: string;
  currency: string;
  active: boolean;
}
interface Lead extends Record<string, unknown> {
  id: number;
  name: string;
  email: string;
  company: string;
  plan: string;
  message: string;
  status: string;
  created_at: string;
}

const STATUS = [
  ["pending", "Pending review"],
  ["approved", "Approved"],
  ["paused", "Paused"],
  ["removed", "Removed"],
] as const;

export function CatalogsTab({ admin }: { admin: boolean }) {
  return (
    <div className="space-y-8">
      <section className="space-y-2" aria-label="Suppliers">
        <h3 className="font-semibold">Suppliers</h3>
        <CrudSection<Supplier>
          path="/staff/suppliers"
          caption="Suppliers"
          empty="No supplier applications yet."
          canCreate={false}
          fields={[
            { name: "name", label: "Name" },
            { name: "description", label: "About", type: "textarea" },
            { name: "website", label: "Website", type: "url" },
            { name: "status", label: "Status", type: "select", options: STATUS },
          ]}
          columns={[
            { header: "Supplier", render: (r) => r.name },
            { header: "Account", render: (r) => r.owner },
            { header: "Status", render: (r) => r.status },
          ]}
        />
      </section>

      <section className="space-y-2" aria-label="3D models">
        <h3 className="font-semibold">3D models</h3>
        <p className="text-sm text-muted">
          Files are structure-checked (GLB 2.0, 8 MB limit) but not malware-scanned, so review each
          one before approving. Approval needs the supplier&rsquo;s rights confirmation.
        </p>
        <CrudSection<Catalog>
          path="/staff/catalogs-3d"
          caption="3D models"
          empty="No models uploaded yet."
          canCreate={false}
          fields={[
            { name: "title", label: "Title" },
            { name: "description", label: "Description", type: "textarea" },
            { name: "collection", label: "Collection" },
            { name: "fallback_image_path", label: "Fallback image path (e.g. /images/x.png)" },
            { name: "rights_confirmed", label: "Rights confirmed", type: "checkbox" },
            { name: "status", label: "Status", type: "select", options: STATUS },
            { name: "reject_reason", label: "Reason if rejected" },
          ]}
          columns={[
            {
              header: "Model",
              render: (r) => (
                <>
                  {r.title}
                  <p className="text-xs text-muted">
                    {r.supplier_name} · {Math.round(r.asset_size / 1024)} KB
                  </p>
                </>
              ),
            },
            {
              header: "Status",
              render: (r) => `${r.status}${r.rights_confirmed ? "" : " (rights not confirmed)"}`,
            },
          ]}
        />
      </section>

      <section className="space-y-2" aria-label="Plans">
        <h3 className="font-semibold">Plans</h3>
        <p className="text-sm text-muted">
          Prices are shown to visitors, but online payment is not switched on: visitors can only
          send an enquiry. Payment providers, tax, invoicing and refund rules must be configured and
          tested before any charge is taken.
        </p>
        <CrudSection<Plan>
          path="/staff/catalog-plans"
          caption="Plans"
          empty="No plans yet."
          newLabel="Add a plan"
          canEdit={admin}
          canCreate={admin}
          fields={[
            { name: "name", label: "Name" },
            {
              name: "kind",
              label: "Model",
              type: "select",
              options: [
                ["one_time", "One-time catalog purchase"],
                ["subscription", "Supplier subscription"],
                ["listing", "Paid listing"],
              ],
            },
            { name: "amount", label: "Price", type: "number" },
            { name: "currency", label: "Currency (ISO 4217)" },
            { name: "description", label: "Description" },
            { name: "active", label: "Show to visitors", type: "checkbox" },
          ]}
          columns={[
            { header: "Plan", render: (r) => r.name },
            { header: "Price", render: (r) => `${r.currency} ${r.amount} (${r.kind})` },
            { header: "Shown", render: (r) => (r.active ? "Yes" : "No") },
          ]}
        />
      </section>

      <section className="space-y-2" aria-label="Enquiries">
        <h3 className="font-semibold">Enquiries</h3>
        <CrudSection<Lead>
          path="/staff/leads"
          caption="Enquiries"
          empty="No enquiries yet."
          canCreate={false}
          canEdit={false}
          fields={[]}
          columns={[
            {
              header: "From",
              render: (r) => (
                <>
                  {r.name}
                  <p className="text-xs text-muted">
                    {r.email}
                    {r.company && ` · ${r.company}`}
                  </p>
                </>
              ),
            },
            {
              header: "Interest",
              render: (r) => (
                <>
                  {r.plan || "General"}
                  {r.message && <p className="text-xs text-muted">{r.message}</p>}
                </>
              ),
            },
            { header: "Status", render: (r) => `${r.status} · ${fmt(r.created_at)}` },
          ]}
          actions={[
            {
              label: "Mark contacted",
              show: (r) => r.status === "new",
              run: (r) => apiSend("POST", `/staff/leads/${r.id}/contacted/`, {}),
            },
            {
              label: "Close",
              show: (r) => r.status !== "closed",
              run: (r) => apiSend("POST", `/staff/leads/${r.id}/closed/`, {}),
            },
          ]}
        />
      </section>
    </div>
  );
}
