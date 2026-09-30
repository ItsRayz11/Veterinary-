import { describe, expect, it } from "vitest";
import { keyToBytes, pushSupported } from "./push";

describe("keyToBytes", () => {
  it("decodes URL-safe base64 without padding", () => {
    // "hello?>" encodes to "aGVsbG8_Pg" in URL-safe base64 (contains the URL-safe "_").
    expect(Array.from(keyToBytes("aGVsbG8_Pg"))).toEqual([104, 101, 108, 108, 111, 63, 62]);
  });

  it("round-trips a 65-byte key length", () => {
    const b64 = btoa(String.fromCharCode(...new Uint8Array(65).fill(7)))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
    expect(keyToBytes(b64)).toHaveLength(65);
  });
});

describe("pushSupported", () => {
  it("is false outside a browser", () => {
    expect(pushSupported()).toBe(false);
  });
});
