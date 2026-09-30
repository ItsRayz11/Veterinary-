import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Same-origin proxy (Django routes end with "/", Next strips it, so it is re-added here) so browser code (search box, calculators, auth cookies) never needs CORS.
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${API_URL}/api/v1/:path*/` }];
  },
};

export default nextConfig;
