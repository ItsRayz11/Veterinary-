import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { upstreamHeaders, upstreamUrl } from "@/lib/api-proxy";

/**
 * Same-origin bridge to the Django API (so browser code never needs CORS and cookies stay
 * first-party). It also forwards the real client IP, proven by a shared secret, so the API's
 * per-IP throttling works behind Vercel's proxies (see api/apps/core/throttling.py).
 */
export function proxy(request: NextRequest) {
  const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";
  const { pathname, search } = request.nextUrl;
  return NextResponse.rewrite(new URL(upstreamUrl(apiUrl, pathname, search)), {
    request: { headers: upstreamHeaders(request.headers, process.env.WEB_PROXY_SECRET) },
  });
}

export const config = { matcher: "/api/v1/:path*" };
