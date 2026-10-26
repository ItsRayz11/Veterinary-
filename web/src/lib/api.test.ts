import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));

import { ApiError, apiGet } from "./api";

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });

function stub(res: Response | Error) {
  const fn = vi.fn(async () => {
    if (res instanceof Error) throw res;
    return res;
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("apiGet", () => {
  it("returns parsed JSON and keeps the revalidate setting", async () => {
    const fn = stub(json([{ slug: "dog" }]));
    expect(await apiGet("/species/", 120)).toEqual([{ slug: "dog" }]);
    const init = (fn.mock.calls[0] as unknown as [string, RequestInit & { next?: object }])[1];
    expect(init.next).toEqual({ revalidate: 120 });
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it("treats a JSON 404 from the API as a missing resource", async () => {
    stub(json({ detail: "Not found." }, 404));
    await expect(apiGet("/drugs/nope/")).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("treats a Vercel platform 404 as service unavailable, not a missing page", async () => {
    stub(new Response("NOT_FOUND", { status: 404, headers: { "x-vercel-error": "NOT_FOUND" } }));
    await expect(apiGet("/species/")).rejects.toMatchObject({ status: 503 });
  });

  it("treats a non-JSON 404 as service unavailable", async () => {
    stub(
      new Response("<html>Not Found</html>", {
        status: 404,
        headers: { "content-type": "text/html" },
      }),
    );
    await expect(apiGet("/species/")).rejects.toMatchObject({ status: 503 });
  });

  it("maps gateway statuses to 503", async () => {
    for (const status of [502, 503, 504]) {
      stub(new Response("x", { status }));
      await expect(apiGet("/species/")).rejects.toMatchObject({ status: 503 });
    }
  });

  it("maps other upstream 5xx to a distinct 502 without leaking the body", async () => {
    stub(new Response("Traceback: secret", { status: 500 }));
    const err = (await apiGet("/species/").catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(502);
    expect(err.message).not.toMatch(/Traceback|secret/);
  });

  it("maps network failure and timeout to 503", async () => {
    stub(new TypeError("fetch failed"));
    await expect(apiGet("/species/")).rejects.toMatchObject({ status: 503 });
    stub(new DOMException("timed out", "TimeoutError"));
    await expect(apiGet("/species/")).rejects.toMatchObject({ status: 503 });
  });

  it("passes other client errors through with their status", async () => {
    stub(json({ detail: "no" }, 403));
    await expect(apiGet("/x/")).rejects.toMatchObject({ status: 403 });
  });
});
