import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MAX_PER_PAGE, isNoise, reportError, resetReporter } from "./report-error";

const fetchMock = vi.fn(() => Promise.resolve(new Response(null, { status: 202 })));

beforeEach(() => {
  resetReporter();
  fetchMock.mockClear();
  vi.stubGlobal("window", { location: { href: "https://site.test/drugs/x?q=secret#frag" } });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const body = () =>
  JSON.parse((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);

describe("reportError", () => {
  it("posts message, stack and page to our own endpoint", () => {
    expect(reportError(new Error("boom"), "Page error")).toBe(true);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/monitoring/client-errors");
    expect(init.method).toBe("POST");
    expect(body().message).toBe("Page error: boom");
    expect(body().url).toContain("/drugs/x");
  });

  it("sends an identical error only once per page load", () => {
    const e = new Error("same");
    expect(reportError(e)).toBe(true);
    expect(reportError(e)).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it(`stops after ${MAX_PER_PAGE} different errors (no flooding)`, () => {
    const results = Array.from({ length: 12 }, (_, i) => reportError(new Error(`e${i}`)));
    expect(results.filter(Boolean)).toHaveLength(MAX_PER_PAGE);
  });

  it("accepts non-Error values and ignores empty ones", () => {
    expect(reportError("plain string failure")).toBe(true);
    expect(body().message).toBe("plain string failure");
    expect(reportError(new Error(""))).toBe(false);
  });

  it("never throws when the network call fails", async () => {
    fetchMock.mockImplementationOnce(() => Promise.reject(new Error("offline")));
    expect(() => reportError(new Error("x1"))).not.toThrow();
    await Promise.resolve();
  });

  it("does nothing outside a browser", () => {
    vi.unstubAllGlobals();
    expect(reportError(new Error("server side"))).toBe(false);
  });
});

describe("isNoise", () => {
  it.each([
    "Script error.",
    "ResizeObserver loop limit exceeded",
    "Failed to fetch",
    "NetworkError when attempting to fetch",
    "Load failed",
  ])("ignores %j", (m) => expect(isNoise(m)).toBe(true));
  it("keeps real errors", () => {
    expect(isNoise("Cannot read properties of undefined (reading 'name')")).toBe(false);
  });
});
