import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));

import { SearchBox } from "./search-box";

const render = (props = {}) => renderToStaticMarkup(<SearchBox {...props} />);

// Regression: /search?q=... rendered an empty input, so the query vanished after submitting.
describe("SearchBox URL synchronisation", () => {
  it("starts empty with no clear button", () => {
    const out = render();
    expect(out).toContain('id="global-search"');
    expect(out).toContain('value=""');
    expect(out).not.toContain("Clear search");
  });

  it("shows the query from the URL and offers a clear button", () => {
    const out = render({ initialQuery: "amoxicillin" });
    expect(out).toContain('value="amoxicillin"');
    expect(out).toContain('aria-label="Clear search"');
  });

  it("escapes special characters instead of injecting markup", () => {
    const out = render({ initialQuery: `a&b "c" <script>x</script>` });
    expect(out).not.toContain("<script>");
    expect(out).toContain("&lt;script&gt;");
    expect(out).toContain("&quot;c&quot;");
  });

  it("keeps the combobox contract and a polite live region for loading and errors", () => {
    const out = render({ initialQuery: "x" });
    expect(out).toContain('role="combobox"');
    expect(out).toContain('aria-live="polite"');
  });
});
