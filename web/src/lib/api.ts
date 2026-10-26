import { notFound } from "next/navigation";

/** Server-side base URL of the Django API. Browser code uses same-origin /api via next.config rewrites. */
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

const TIMEOUT_MS = 10_000;

/**
 * A 404 is a genuine "no such record" only when the Django API itself answered: DRF replies with
 * JSON and the response carries no `x-vercel-error`. A platform 404 (no deployment behind
 * API_URL, wrong host or prefix) is a plain-text/HTML page, which means the service is down or
 * misconfigured, not that the visitor asked for something missing.
 */
function isApiNotFound(res: Response): boolean {
  return (
    !res.headers.has("x-vercel-error") &&
    (res.headers.get("content-type") ?? "").includes("application/json")
  );
}

export async function apiGet<T>(path: string, revalidate = 60): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, {
      next: { revalidate },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    throw new ApiError("The data service is currently unreachable.", 503);
  }
  if (res.status === 404) {
    if (isApiNotFound(res)) notFound();
    throw new ApiError("The data service is currently unreachable.", 503);
  }
  if (res.status === 502 || res.status === 503 || res.status === 504) {
    throw new ApiError("The data service is currently unreachable.", 503);
  }
  if (res.status >= 500) {
    throw new ApiError("The data service returned an unexpected error.", 502);
  }
  if (!res.ok) throw new ApiError(`Data service returned ${res.status}.`, res.status);
  return (await res.json()) as T;
}

export interface Status {
  code: string;
  label: string;
  is_development_data: boolean;
  is_unverified_import?: boolean;
  reviewed_at: string | null;
}

export interface SourceRef {
  id: number;
  title: string;
  publisher: string;
  url: string;
  doi: string;
  type: string;
  publication_date: string | null;
  locator: string;
}

export interface Brand {
  brand_name: string;
  slug: string;
  generic: string;
  generic_name: string;
  manufacturer: { name: string; slug: string; country: string };
  countries: string[];
  status: Status;
}

export interface Dose {
  id: number;
  species: string;
  species_name: string;
  indication: string | null;
  route: string;
  country: string | null;
  dose_min: string;
  dose_max: string;
  dose_unit: string;
  interval_hours: string | null;
  duration_min_days: number | null;
  duration_max_days: number | null;
  max_single_dose: string | null;
  max_single_dose_unit: string | null;
  notes: string;
  status: Status;
  calculator_ready: boolean;
  sources: SourceRef[];
}

export interface Note {
  id: number;
  kind: string;
  species: string | null;
  text: string;
  status: Status;
  sources: SourceRef[];
}

export interface GenericDetail {
  name: string;
  slug: string;
  drug_class: string | null;
  synonyms: string[];
  ingredients: string[];
  description: string;
  mechanism: string;
  status: Status;
  sources: SourceRef[];
  doses: Dose[];
  notes: Note[];
  brands: Brand[];
  disclaimer: string;
}

export interface ProductDetail extends Brand {
  category: string;
  description: string;
  is_biologic: boolean;
  marketing_holder: string | null;
  ingredients: {
    name: string;
    strength: string;
    unit: string;
    per: string | null;
    per_value: string;
  }[];
  packs: { form: string; size: string; unit: string }[];
  registrations: { country: string; number: string; status: string; record_status: Status }[];
  withdrawal_periods: {
    country: string;
    species: string;
    commodity: string;
    route: string;
    duration_value: string;
    duration_unit: string;
    regimen_note: string;
    regulatory_status: string;
    status: Status;
  }[];
  sources: SourceRef[];
}

export interface CompanyDetail {
  name: string;
  slug: string;
  country: string;
  website: string;
  description: string;
  roles: string[];
  verified_profile: boolean;
  status: Status;
  products: Brand[];
}

export interface PriceRow {
  id: number;
  pack: string;
  pack_id: number;
  country: string;
  region: string;
  city: string;
  currency: string;
  price_type: string;
  amount: string;
  origin: string;
  source: { title: string; url: string } | null;
  observed_on: string;
  last_verified: string | null;
}

export interface PriceSeries {
  pack_id: number;
  pack: string;
  country: string;
  region: string;
  city: string;
  price_type: string;
  currency: string;
  points: { date: string; amount: string }[];
  latest: string;
  min: string;
  max: string;
  change: string | null;
  change_percent: string | null;
  direction: "up" | "down" | "same" | "none";
}

export interface RegionComparison {
  pack: string;
  country: string;
  price_type: string;
  currency: string;
  regions: { region: string; amount: string; observed_on: string }[];
  spread: string;
  spread_percent: string;
}

export interface Prices {
  current: PriceRow[];
  history: PriceRow[];
  analytics: { series: PriceSeries[]; region_comparison: RegionComparison[] };
  note: string;
}
