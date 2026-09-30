import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { StatusBadge } from "./status-badge";

describe("StatusBadge", () => {
  it("labels development data as not verified", () => {
    const html = renderToStaticMarkup(createElement(StatusBadge, { status: "development" }));
    expect(html).toContain("not verified");
  });
});
