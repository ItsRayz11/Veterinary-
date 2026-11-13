import type { ReactNode } from "react";

/**
 * Renders the article text subset: "#"/"##"/"###" headings, "- " lists, paragraphs, [text](https://…)
 * links and ![alt](/same-site-path) images. Everything is React text, never HTML, so nothing an
 * author types can run script. Only https links and same-site image paths become elements.
 */
const TOKEN = /(!\[[^\]]*\]\(\/[^)\s]*\)|\[[^\]]+\]\(https:\/\/[^)\s]+\))/g;

export function inline(text: string): ReactNode[] {
  return text.split(TOKEN).map((part, i) => {
    const img = /^!\[([^\]]*)\]\((\/[^)\s]*)\)$/.exec(part);
    if (img && !img[2].startsWith("//"))
      // eslint-disable-next-line @next/next/no-img-element
      return <img key={i} src={img[2]} alt={img[1]} loading="lazy" className="my-3 rounded-lg" />;
    const link = /^\[([^\]]+)\]\((https:\/\/[^)\s]+)\)$/.exec(part);
    if (link)
      return (
        <a
          key={i}
          href={link[2]}
          rel="noopener noreferrer nofollow ugc"
          target="_blank"
          className="text-primary underline"
        >
          {link[1]}
        </a>
      );
    return part;
  });
}

export function ArticleBody({ text }: { text: string }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return (
    <div className="space-y-3 leading-relaxed">
      {blocks.map((b, i) => {
        const t = b.trim();
        if (!t) return null;
        const h = /^(#{1,3})\s+(.+)$/.exec(t);
        if (h) {
          const cls = "mt-4 font-semibold tracking-tight";
          return h[1].length === 1 ? (
            <h2 key={i} className={`${cls} text-xl`}>
              {inline(h[2])}
            </h2>
          ) : (
            <h3 key={i} className={`${cls} text-lg`}>
              {inline(h[2])}
            </h3>
          );
        }
        const lines = t.split("\n");
        if (lines.every((l) => /^[-*]\s+/.test(l)))
          return (
            <ul key={i} className="list-disc space-y-1 pl-5">
              {lines.map((l, j) => (
                <li key={j}>{inline(l.replace(/^[-*]\s+/, ""))}</li>
              ))}
            </ul>
          );
        return <p key={i}>{inline(t)}</p>;
      })}
    </div>
  );
}
