import type { NextConfig } from "next";
import { adsConfig } from "./src/lib/ads";
import { securityHeaders } from "./src/lib/security-headers";

const nextConfig: NextConfig = {
  images: {
    // University photos and logos are openly licensed Wikimedia Commons files, served through
    // /_next/image so the CSP can keep `img-src 'self'`.
    remotePatterns: [
      { protocol: "https", hostname: "upload.wikimedia.org" },
      { protocol: "https", hostname: "thumb.wikimedia.org" },
      // Approved images copied to Cloudflare R2 (public custom domain / r2.dev host, no scheme).
      ...(process.env.NEXT_PUBLIC_R2_PUBLIC_HOST
        ? [{ protocol: "https" as const, hostname: process.env.NEXT_PUBLIC_R2_PUBLIC_HOST }]
        : []),
    ],
  },
  // There are no index pages for these sections (slug routes only). Temporary (307) redirects keep
  // the choice reversible; slug routes such as /drugs/<slug> are unaffected.
  async redirects() {
    return [
      { source: "/drugs", destination: "/classes", permanent: false },
      { source: "/products", destination: "/search", permanent: false },
      { source: "/companies", destination: "/search", permanent: false },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders(process.env.NODE_ENV === "production", adsConfig().enabled),
      },
      // The worker must always be revalidated so updates reach users promptly.
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
        ],
      },
    ];
  },
  // The /api/v1/* bridge to the Django API lives in src/proxy.ts (it also forwards the real
  // client IP for throttling), so no rewrites are configured here.
};

export default nextConfig;
