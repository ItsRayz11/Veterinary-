import type { MetadataRoute } from "next";
import { CALCULATORS } from "@/lib/calc/registry";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-dynamic";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

interface Page<T> {
  results: T[];
  next: string | null;
}

/** Reads a plain list or a paginated list (following `next`, capped) from the API. */
async function list<T>(path: string): Promise<T[]> {
  const out: T[] = [];
  let url: string | null = `${API_URL}/api/v1${path}`;
  try {
    for (let i = 0; url && i < 40; i++) {
      const res: Response = await fetch(url, { next: { revalidate: 3600 } });
      if (!res.ok) break;
      const data = (await res.json()) as T[] | Page<T>;
      if (Array.isArray(data)) return data;
      out.push(...data.results);
      url = data.next;
    }
  } catch {
    // API unreachable: still serve the static part of the sitemap
  }
  return out;
}

/** Only reviewed/public records are returned by these endpoints, so nothing unreviewed is listed. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [species, classes, countries, generics, lessons, jobs, scholarships] = await Promise.all([
    list<{ slug: string }>("/species/"),
    list<{ slug: string }>("/drug-classes/"),
    list<{ iso2: string }>("/countries/"),
    list<{ slug: string }>("/generics/"),
    list<{ slug: string }>("/study/lessons/"),
    list<{ id: number }>("/listings/jobs/"),
    list<{ id: number }>("/listings/scholarships/"),
  ]);
  const paths = [
    "/",
    "/search",
    "/calculators",
    "/calculators/dose-calculator",
    ...CALCULATORS.map((c) => `/calculators/${c.slug}`),
    "/species",
    ...species.map((s) => `/species/${s.slug}`),
    "/classes",
    ...classes.map((c) => `/classes/${c.slug}`),
    "/countries",
    ...countries.map((c) => `/countries/${c.iso2}`),
    "/study",
    "/study/past-papers",
    "/study/lessons",
    ...lessons.map((l) => `/study/lessons/${l.slug}`),
    "/study/books",
    "/jobs",
    ...jobs.map((j) => `/jobs/${j.id}`),
    "/scholarships",
    ...scholarships.map((j) => `/scholarships/${j.id}`),
    ...generics.map((g) => `/drugs/${g.slug}`),
  ];
  return paths.map((p) => ({ url: `${SITE_URL}${p}` }));
}
