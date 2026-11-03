import type { Metadata } from "next";
import { apiGetAll, type UniversityBrief } from "@/lib/api";
import credits from "@/lib/image-credits.json";
import { Breadcrumbs, DataTable, PageHeader, Section, td, th } from "@/components/ui/primitives";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Image and data credits",
  description:
    "Sources and licences for the photographs, flags, maps, icons and text used on VetRef.",
  alternates: { canonical: "/credits" },
};

interface SpeciesCredit {
  file: string;
  source_article: string;
  page: string;
  credit: string;
  license: string;
  license_url: string;
}

const ext = { rel: "noopener noreferrer", target: "_blank" } as const;

export default async function CreditsPage() {
  const species = Object.entries((credits as { species: Record<string, SpeciesCredit> }).species);
  let unis: UniversityBrief[] = [];
  try {
    unis = (await apiGetAll<UniversityBrief>("/universities/")).filter((u) => u.image);
  } catch {
    // The data service being down must not take the credits page down.
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Credits" }]} />
      <PageHeader
        title="Image and data credits"
        lead="Every photograph, flag, map and block of text from another source is listed here with its licence."
      />

      <Section id="general" title="Flags, maps, icons and text">
        <ul className="list-disc space-y-2 pl-5 text-sm">
          <li>
            Flags:{" "}
            <a className="underline" href="https://github.com/lipis/flag-icons" {...ext}>
              flag-icons
            </a>{" "}
            by Panayiotis Lipiridis and contributors, MIT licence.
          </li>
          <li>
            Country outlines: drawn from{" "}
            <a className="underline" href="https://www.naturalearthdata.com/" {...ext}>
              Natural Earth
            </a>{" "}
            1:50m boundaries via the world-atlas package, public domain. Outlines are for
            orientation and do not express a position on any boundary.
          </li>
          <li>
            Icons:{" "}
            <a className="underline" href="https://lucide.dev/" {...ext}>
              Lucide
            </a>
            , ISC licence.
          </li>
          <li>
            University summaries, websites and coordinates:{" "}
            <a className="underline" href="https://www.wikipedia.org/" {...ext}>
              Wikipedia
            </a>{" "}
            text under{" "}
            <a
              className="underline"
              href="https://creativecommons.org/licenses/by-sa/4.0/"
              {...ext}
            >
              CC BY-SA 4.0
            </a>
            , and{" "}
            <a className="underline" href="https://www.wikidata.org/" {...ext}>
              Wikidata
            </a>{" "}
            (CC0). These records are labelled as imported until a reviewer checks them.
          </li>
        </ul>
      </Section>

      <Section id="species" title="Species photographs">
        <DataTable caption="Species photographs, authors and licences">
          <thead>
            <tr>
              <th className={th}>Species</th>
              <th className={th}>Author</th>
              <th className={th}>Licence</th>
              <th className={th}>Source</th>
            </tr>
          </thead>
          <tbody>
            {species.map(([slug, c]) => (
              <tr key={slug}>
                <td className={`${td} capitalize`}>{slug}</td>
                <td className={td}>{c.credit}</td>
                <td className={td}>
                  {c.license_url ? (
                    <a className="underline" href={c.license_url} {...ext}>
                      {c.license}
                    </a>
                  ) : (
                    c.license
                  )}
                </td>
                <td className={td}>
                  <a className="underline" href={c.page} {...ext}>
                    Wikimedia Commons
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </Section>

      {unis.length > 0 && (
        <Section id="universities" title="University images">
          <DataTable caption="University images, authors and licences">
            <thead>
              <tr>
                <th className={th}>University</th>
                <th className={th}>Author</th>
                <th className={th}>Licence</th>
                <th className={th}>Source</th>
              </tr>
            </thead>
            <tbody>
              {unis.map((u) => (
                <tr key={u.slug}>
                  <td className={td}>{u.name}</td>
                  <td className={td}>{u.image!.credit}</td>
                  <td className={td}>
                    {u.image!.license_url ? (
                      <a className="underline" href={u.image!.license_url} {...ext}>
                        {u.image!.license}
                      </a>
                    ) : (
                      u.image!.license
                    )}
                  </td>
                  <td className={td}>
                    <a className="underline" href={u.image!.page_url} {...ext}>
                      Wikimedia Commons
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </Section>
      )}
    </div>
  );
}
