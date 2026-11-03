/**
 * Public origin of the web app. Set NEXT_PUBLIC_SITE_URL in production; on Vercel the production
 * domain is used when it is unset, so canonical/OG/sitemap URLs are never `localhost`.
 */
const configured =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000");

export const SITE_URL = configured.replace(/\/$/, "");
