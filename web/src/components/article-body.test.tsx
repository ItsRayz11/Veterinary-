import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ArticleBody } from "./article-body";

const html = (t: string) => renderToStaticMarkup(<ArticleBody text={t} />);

describe("ArticleBody", () => {
  it("never emits author-supplied HTML", () => {
    const out = html("<script>alert(1)</script> <img src=x onerror=alert(1)>");
    expect(out).not.toContain("<script");
    expect(out).not.toContain("<img");
    expect(out).toContain("&lt;script&gt;");
  });

  it("only links https and only embeds same-site images", () => {
    const out = html(
      "[bad](javascript:alert(1)) [ok](https://example.org/x) ![a](https://evil.org/a.png) ![b](//evil.org/b.png) ![c](/images/c.png)",
    );
    expect(out).not.toContain('href="javascript');
    expect(out).toContain('href="https://example.org/x"');
    expect(out).toContain('rel="noopener noreferrer nofollow ugc"');
    expect(out).not.toContain('src="https'); // remote images become plain links
    expect(out).not.toContain('src="//evil.org');
    expect(out).toContain('src="/images/c.png"');
  });

  it("renders headings and lists", () => {
    const out = html("# Title\n\n- one\n- two\n\nPara");
    expect(out).toContain("<h2");
    expect(out).toContain("<ul");
    expect(out).toContain("<p>Para</p>");
  });
});
