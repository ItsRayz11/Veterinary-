export type Kind = "jobs" | "scholarships";

export interface Listing {
  id: number;
  kind: Kind;
  title: string;
  organization: string;
  country: string | null;
  country_name: string | null;
  description: string;
  apply_url: string;
  closes_on: string | null;
  expires_on: string | null;
  // jobs
  city?: string;
  job_type?: string;
  // scholarships
  level?: string;
  funding?: string;
}

export const LABELS: Record<Kind, { plural: string; singular: string; newPath: string }> = {
  jobs: { plural: "Jobs", singular: "job", newPath: "/jobs/new" },
  scholarships: { plural: "Scholarships", singular: "scholarship", newPath: "/scholarships/new" },
};

export const JOB_TYPES = [
  ["full_time", "Full time"],
  ["part_time", "Part time"],
  ["contract", "Contract"],
  ["internship", "Internship"],
  ["volunteer", "Volunteer"],
] as const;

export const LEVELS = [
  ["dvm", "DVM / BVSc"],
  ["masters", "Masters"],
  ["phd", "PhD"],
  ["postdoc", "Postdoctoral"],
  ["short_course", "Short course / training"],
  ["other", "Other"],
] as const;

export const FUNDING = [
  ["full", "Fully funded"],
  ["partial", "Partially funded"],
  ["unknown", "Not stated"],
] as const;

export const label = (pairs: readonly (readonly [string, string])[], v?: string) =>
  pairs.find(([k]) => k === v)?.[1] ?? v ?? "";
