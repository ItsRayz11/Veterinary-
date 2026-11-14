import { adsTxt } from "@/lib/ads";

export const dynamic = "force-dynamic";

export function GET() {
  const body = adsTxt();
  if (!body) return new Response("Not found", { status: 404 });
  return new Response(body, { headers: { "content-type": "text/plain; charset=utf-8" } });
}
