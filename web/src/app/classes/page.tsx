import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { Breadcrumbs, EmptyState } from "@/components/ui/primitives";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Drug classes",
  description: "Browse veterinary medicines by pharmacological class.",
  alternates: { canonical: "/classes" },
};

interface ClassRow {
  slug: string;
  name: string;
  parent: string | null;
  generic_count: number;
}

function Tree({ rows, parent }: { rows: ClassRow[]; parent: string | null }) {
  const level = rows.filter((r) => r.parent === parent);
  if (!level.length) return null;
  return (
    <ul className={parent ? "ml-5 mt-1 space-y-1" : "space-y-2"}>
      {level.map((c) => (
        <li key={c.slug}>
          <Link className="text-primary underline" href={`/classes/${c.slug}`}>
            {c.name}
          </Link>{" "}
          <span className="text-xs text-muted">({c.generic_count})</span>
          <Tree rows={rows} parent={c.slug} />
        </li>
      ))}
    </ul>
  );
}

export default async function ClassesIndex() {
  const rows = await apiGet<ClassRow[]>("/drug-classes/");
  return (
    <div className="space-y-4">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Drug classes" }]} />
      <h1 className="text-2xl font-semibold">Drug classes</h1>
      {rows.length === 0 ? (
        <EmptyState title="No drug classes available yet." />
      ) : (
        <Tree rows={rows} parent={null} />
      )}
    </div>
  );
}
