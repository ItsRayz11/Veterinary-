import type { NextConfig } from "next";
import { securityHeaders } from "./src/lib/security-headers";

const nextConfig: NextConfig = {
  images: {
    // University photos and logos are openly licensed Wikimedia Commons files, served through
    // /_next/image so the CSP can keep `img-src 'self'`.
    remotePatterns: [
      { protocol: "https", hostname: "upload.wikimedia.org" },
      { protocol: "https", hostname: "thumb.wikimedia.org" },
    ],
  },
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders(process.env.NODE_ENV === "production") },
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
