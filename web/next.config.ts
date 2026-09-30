import type { NextConfig } from "next";
import { securityHeaders } from "./src/lib/security-headers";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
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
  // Same-origin proxy (Django routes end with "/", Next strips it, so it is re-added here) so browser code (search box, calculators, auth cookies) never needs CORS.
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${API_URL}/api/v1/:path*/` }];
  },
};

export default nextConfig;
