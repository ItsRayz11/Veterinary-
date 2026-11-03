import type { Metadata } from "next";
import Link from "next/link";
import { CalendarDays, ExternalLink, Globe, MapPin } from "lucide-react";
import { apiGet, type UniversityDetail } from "@/lib/api";
import { JsonLd } from "@/components/json-ld";
import { StatusLine } from "@/components/status-line";
import { Flag } from "@/components/ui/flag";
import { Alert, Breadcrumbs, EmptyState, Section } from "@/components/ui/primitives";
import { UniversityImageBox } from "@/components/ui/university-card";
import { DocumentCard, MetadataBadge, RelatedResources } from "@/components/ui/visual";
import { SITE_URL } from "@/lib/site";

export async function generateMetadata({
  params,
}: PageProps<"/universities/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const u = await apiGet<UniversityDetail>(`/universities/${slug}/`);
  return {
    title: u.name,
    description: `${u.name}${u.city ? `, ${u.city}` : ""}, ${u.country_name}: veterinary education, official website and linked past papers.`,
    alternates: { canonical: `/universities/${u.slug}` },
    robots: { index: !u.status.is_unverified_import },
  };
}

export default async function UniversityPage({ params }: PageProps<"/universities/[slug]">) {
  const { slug } = await params;
  const u = await apiGet<UniversityDetail>(`/universities/${slug}/`);
  const indexable = !u.status.is_unverified_import && !u.status.is_development_data;
  const osm =
    u.latitude && u.longitude
      ? `https://www.openstreetmap.org/?mlat=${u.latitude}&mlon=${u.longitude}#map=12/${u.latitude}/${u.longitude}`
      : "";

  return (
    <div className="space-y-6">
      {indexable && (
        <JsonLd
          data={{
            "@context": "https://schema.org",
            "@type": "CollegeOrUniversity",
            name: u.name,
            url: `${SITE_URL}/universities/${u.slug}`,
            ...(u.website ? { sameAs: [u.website] } : {}),
            ...(u.city ? { address: { "@type": "PostalAddress", addressLocality: u.city } } : {}),
          }}
        />
      )}
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Universities", href: "/universities" },
          { label: u.name },
        ]}
      />

      <header className="glass overflow-hidden rounded-[var(--radius-xl)]">
        <div className="grid md:grid-cols-[1fr_20rem]">
          <div className="space-y-3 p-5 sm:p-8">
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{u.name}</h1>
            <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
              <Link
                href={`/countries/${u.country}`}
                className="inline-flex items-center gap-1.5 hover:underline"
              >
                <Flag iso2={u.country} name={u.country_name} className="h-4 w-6" />
                {u.country_name}
              </Link>
              {u.city && (
                <span className="inline-flex items-center gap-1">
                  <MapPin size={14} aria-hidden="true" />
                  {u.city}
                </span>
              )}
              {u.founded_year && (
                <span className="inline-flex items-center gap-1">
                  <CalendarDays size={14} aria-hidden="true" />
                  Founded {u.founded_year}
                </span>
              )}
            </p>
            <StatusLine status={u.status} />
            <div className="flex flex-wrap gap-2 pt-1">
              {u.website && (
                <a
                  href={u.website}
                  rel="noopener noreferrer nofollow"
                  target="_blank"
                  className="inline-flex min-h-11 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-fg"
                >
                  <Globe size={16} aria-hidden="true" />
                  Official website
                  <span className="sr-only">(opens external site)</span>
                </a>
              )}
              {osm && (
                <a
                  href={osm}
                  rel="noopener noreferrer"
                  target="_blank"
                  className="neo inline-flex min-h-11 items-center gap-2 rounded-md px-4 text-sm"
                >
                  <MapPin size={16} aria-hidden="true" />
                  View on map
                  <span className="sr-only">(opens OpenStreetMap)</span>
                </a>
              )}
            </div>
          </div>
          <div className="relative min-h-44 bg-surface-2">
            <UniversityImageBox uni={u} sizes="(min-width: 768px) 20rem, 100vw" priority />
          </div>
        </div>
        {u.image && (
          <p className="border-t border-border px-5 py-2 text-xs text-muted sm:px-8">
            Image: {u.image.credit}, {u.image.license}
            {u.image.page_url && (
              <>
                {" · "}
                <a
                  href={u.image.page_url}
                  rel="noopener noreferrer"
                  target="_blank"
                  className="underline"
                >
                  Source on Wikimedia Commons
                </a>
              </>
            )}
            {u.image.license_url && (
              <>
                {" · "}
                <a
                  href={u.image.license_url}
                  rel="noopener noreferrer"
                  target="_blank"
                  className="underline"
                >
                  Licence
                </a>
              </>
            )}
          </p>
        )}
      </header>

      {u.status.is_unverified_import && (
        <Alert tone="warn" title="Imported, not reviewed">
          This record was imported from Wikipedia and Wikidata and has not been checked by a
          reviewer. Confirm programmes, accreditation and admissions on the university&apos;s own
          website.
        </Alert>
      )}

      {u.summary && (
        <Section id="about" title={`About ${u.name}`} category="universities">
          <p className="max-w-3xl text-sm leading-relaxed">{u.summary}</p>
          <p className="mt-2 text-xs text-muted">
            Summary from{" "}
            <a
              href={u.source_url}
              rel="noopener noreferrer"
              target="_blank"
              className="inline-flex items-center gap-0.5 underline"
            >
              Wikipedia
              <ExternalLink size={11} aria-hidden="true" />
            </a>
            , {u.source_license}. Check the university&apos;s own website for current programmes and
            admissions.
          </p>
        </Section>
      )}

      <Section id="papers" title="Past papers and study resources" category="papers">
        {u.past_papers.length ? (
          <ul className="grid gap-3 sm:grid-cols-2">
            {u.past_papers.map((p) => (
              <li key={p.url}>
                <DocumentCard
                  href={p.url}
                  title={p.course}
                  source={u.name}
                  note={p.license_note}
                  badges={
                    <>
                      {p.exam_type && <MetadataBadge tone="blue">{p.exam_type}</MetadataBadge>}
                      {p.degree && <MetadataBadge>{p.degree}</MetadataBadge>}
                      <MetadataBadge>{p.year}</MetadataBadge>
                    </>
                  }
                />
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No past papers indexed for this university yet.">
            Papers are linked only with a legal source and licence note.
          </EmptyState>
        )}
      </Section>

      <RelatedResources
        items={[
          { href: "/study/past-papers", label: "All past papers", category: "papers" },
          { href: "/study", label: "Mock exams", category: "mocktests" },
          { href: `/countries/${u.country}`, label: u.country_name, category: "countries" },
          { href: "/scholarships", label: "Scholarships", category: "scholarships" },
        ]}
      />
    </div>
  );
}
