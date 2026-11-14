/**
 * Official public origin of the web app. NEXT_PUBLIC_SITE_URL overrides it (e.g. for previews);
 * otherwise production builds use the official domain so canonical/OG/sitemap URLs are never
 * `localhost` or a *.vercel.app address.
 */
export const OFFICIAL_SITE_URL = "https://vetsphere.xyz";

const configured =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:3000" : OFFICIAL_SITE_URL);

export const SITE_URL = configured.replace(/\/$/, "");
