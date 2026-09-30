import { describe, expect, it } from "vitest";
import { safeNext } from "./safe-next";

const ORIGIN = "https://vetref.example";

describe("safeNext", () => {
  it.each([
    ["/account", "/account"],
    ["/study/exams/3", "/study/exams/3"],
    ["/search?q=enro", "/search?q=enro"],
    ["/drugs/x#dosing", "/drugs/x#dosing"],
    ["/", "/"],
    ["/%5Cevil.com", "/%5Cevil.com"], // percent-encoded backslash stays a path on this site
  ])("keeps the same-site path %j", (input, expected) => {
    expect(safeNext(input, ORIGIN)).toBe(expected);
  });

  it.each([
    null,
    "",
    "//evil.com",
    "//evil.com/path",
    "/\\evil.com", // browsers read the backslash as a slash
    "/\\/evil.com",
    "/\t/evil.com", // tabs are stripped by URL parsing
    "/\n/evil.com",
    "https://evil.com",
    "http://vetref.example.evil.com",
    "javascript:alert(1)",
    "evil.com",
    "account",
    "\\\\evil.com",
  ])("falls back to / for %j", (input) => {
    expect(safeNext(input, ORIGIN)).toBe("/");
  });
});
