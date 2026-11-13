import type { Metadata } from "next";
import { SupplierArea } from "@/components/supplier-area";
import { Breadcrumbs } from "@/components/ui/primitives";

export const metadata: Metadata = {
  title: "Supplier area",
  robots: { index: false },
  alternates: { canonical: "/catalogs-3d/supplier" },
};

export default function Page() {
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "3D catalogs", href: "/catalogs-3d" },
          { label: "Supplier area" },
        ]}
      />
      <h1 className="text-2xl font-semibold tracking-tight">Supplier area</h1>
      <SupplierArea />
    </div>
  );
}
