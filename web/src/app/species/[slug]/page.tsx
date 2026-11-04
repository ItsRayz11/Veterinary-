import type { Metadata } from "next";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { SpeciesPhoto, speciesCredit } from "@/components/ui/species-photo";
import { HelpTip } from "@/components/ui/help-tip";
import { RelatedResources } from "@/components/ui/visual";
import { Alert, Breadcrumbs, DataTable, td, th } from "@/components/ui/primitives";

interface SpeciesDetail {
  slug: string;
  name: string;
  is_food_producing: boolean;
  parent: { slug: string; name: string } | null;
  children: { slug: string; name: string }[];
  generics: { name: string; slug: string; drug_class: string | null; dose_count: number }[];
  authorized_medicines: {
    slug: string;
    name: string;
    drug_class: string | null;
    authorizations: number;
    in_force: number;
    countries: string[];
    unverified: boolean;
  }[];
}

export async function generateMetadata({
  params,
}: PageProps<"/species/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const s = await apiGet<SpeciesDetail>(`/species/${slug}/`);
  return { title: s.name, alternates: { canonical: `/species/${s.slug}` } };
}

export default async function SpeciesPage({ params }: PageProps<"/species/[slug]">) {
  const { slug } = await params;
  const raw = await apiGet<SpeciesDetail>(`/species/${slug}/`);
  // A cached response from before the field existed must not break the page.
  const s = { ...raw, authorized_medicines: raw.authorized_medicines ?? [] };
  return (
    <div className="space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Species", href: "/species" },
          ...(s.parent ? [{ label: s.parent.name, href: `/species/${s.parent.slug}` }] : []),
          { label: s.name },
        ]}
      />
      <div className="flex items-center gap-4">
        <SpeciesPhoto
          slug={s.slug}
          name={s.name}
          sizes="160px"
          priority
          className="h-24 w-32 shrink-0 rounded-xl sm:h-28 sm:w-40"
        />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{s.name}</h1>
          {speciesCredit(s.slug) && (
            <p className="mt-1 text-xs text-muted">
              Photo: {speciesCredit(s.slug)!.credit}, {speciesCredit(s.slug)!.license}.{" "}
              <Link href="/credits" className="underline">
                Credits
              </Link>
            </p>
          )}
        </div>
      </div>
      <RelatedResources
        items={[
          {
            href: "/calculators/dose-calculator",
            label: "Dose calculator",
            category: "calculators",
          },
          { href: "/classes", label: "Drug classes", category: "classes" },
          { href: "/countries", label: "Countries", category: "countries" },
        ]}
      />
      {s.is_food_producing && (
        <Alert tone="warn" title="Food-producing species">
          Withdrawal periods apply; see each product page.
        </Alert>
      )}
      {s.children.length > 0 && (
        <p className="flex flex-wrap gap-3 text-sm">
          {s.children.map((c) => (
            <Link key={c.slug} className="text-primary underline" href={`/species/${c.slug}`}>
              {c.name}
            </Link>
          ))}
        </p>
      )}
      {s.authorized_medicines.length > 0 && (
        <section aria-labelledby="authorized" className="space-y-2">
          <h2 id="authorized" className="flex items-center gap-1 font-semibold">
            Authorised medicines ({s.authorized_medicines.length})
            <HelpTip label="About authorised medicines">
              Each product authorisation lists its target species as stated by the regulator. The
              same ingredient may be authorised for other animals only under a different product.
              Entries marked &ldquo;not reviewed&rdquo; are imported and not yet checked by a
              reviewer.
            </HelpTip>
          </h2>
          <DataTable caption={`Medicines with a regulator-stated authorisation for ${s.name}`}>
            <thead>
              <tr>
                <th className={th}>Drug</th>
                <th className={th}>Class</th>
                <th className={th}>Products</th>
                <th className={th}>Countries</th>
              </tr>
            </thead>
            <tbody>
              {s.authorized_medicines.map((m) => (
                <tr key={m.slug}>
                  <td className={td}>
                    <Link className="text-primary underline" href={`/drugs/${m.slug}`}>
                      {m.name}
                    </Link>
                    {m.unverified && <span className="ml-2 text-xs text-muted">not reviewed</span>}
                  </td>
                  <td className={td}>{m.drug_class ?? ""}</td>
                  <td className={td}>{m.authorizations}</td>
                  <td className={td}>{m.countries.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </section>
      )}
      {s.generics.length > 0 ? (
        <section aria-labelledby="doses" className="space-y-2">
          <h2 id="doses" className="flex items-center gap-1 font-semibold">
            Reviewed dose references
            <HelpTip label="About species dosing">
              Drugs appear here only when a sourced, veterinarian-reviewed dose exists for {s.name}.
              Doses are never copied from another species or inferred from a drug name.
            </HelpTip>
          </h2>
          <DataTable caption={`Drugs with reviewed doses for ${s.name}`}>
            <thead>
              <tr>
                <th className={th}>Drug</th>
                <th className={th}>Class</th>
                <th className={th}>Doses</th>
              </tr>
            </thead>
            <tbody>
              {s.generics.map((g) => (
                <tr key={g.slug}>
                  <td className={td}>
                    <Link
                      className="text-primary underline"
                      href={`/drugs/${g.slug}?species=${s.slug}`}
                    >
                      {g.name}
                    </Link>
                  </td>
                  <td className={td}>{g.drug_class ?? ""}</td>
                  <td className={td}>{g.dose_count}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </section>
      ) : (
        <p className="text-sm text-muted">
          No reviewed dose references for {s.name} yet. Doses are published only after sourcing and
          veterinary review.
        </p>
      )}
      {s.authorized_medicines.some((m) => m.countries.includes("GB")) && (
        <p className="text-xs text-muted">
          Sources: UK Veterinary Medicines Directorate Product Information Database. Contains public
          sector information licensed under the{" "}
          <a
            className="underline"
            href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
          >
            Open Government Licence v3.0
          </a>
          .
        </p>
      )}
    </div>
  );
}
