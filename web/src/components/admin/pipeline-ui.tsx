"use client";

import { ExternalLink } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

/** Short, readable form of a URL: host plus a truncated path. The full address stays in the
 * title and in the link itself, so nothing is lost and nothing can stretch the layout. */
export function shortUrl(url: string, max = 56): string {
  try {
    const u = new URL(url);
    const rest = decodeURIComponent(`${u.pathname}${u.search}`).replace(/\/$/, "");
    const text = `${u.hostname.replace(/^www\./, "")}${rest}`;
    return text.length > max ? `${text.slice(0, max - 1)}…` : text;
  } catch {
    return url.length > max ? `${url.slice(0, max - 1)}…` : url;
  }
}

export const isHttp = (u: string) => /^https?:\/\//i.test(u);

/** An outbound link that never breaks the layout. Non-http(s) values render as plain text. */
export function SafeLink({
  href,
  label,
  className = "",
}: {
  href: string;
  label?: string;
  className?: string;
}) {
  if (!href) return <span className="text-muted">(none)</span>;
  if (!isHttp(href)) return <span className="break-words">{href}</span>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title={href}
      className={`inline-flex min-w-0 max-w-full items-center gap-1 text-primary underline ${className}`}
    >
      <span className="min-w-0 truncate">{label ?? shortUrl(href)}</span>
      <ExternalLink aria-hidden className="size-3 shrink-0" />
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

const TONES = {
  ok: "bg-ok-bg text-ok",
  warn: "bg-warn-bg text-warn",
  danger: "bg-danger-bg text-danger",
  info: "bg-info-bg text-info",
  muted: "bg-black/5 text-muted",
} as const;
export type Tone = keyof typeof TONES;

export function Badge({ tone = "muted", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex max-w-full items-center rounded px-1.5 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      <span className="min-w-0 truncate">{children}</span>
    </span>
  );
}

export const SOURCE_TONE: Record<string, [Tone, string]> = {
  linked_ok: ["ok", "Source verified"],
  linked_unverified: ["warn", "Source not verified"],
  raw_url_only: ["danger", "URL not linked"],
  none: ["danger", "No source"],
  conflict: ["danger", "Conflicting evidence"],
  invalid: ["danger", "Invalid source"],
};
export const IMAGE_TONE: Record<string, [Tone, string]> = {
  none: ["muted", "No image"],
  pending: ["warn", "Image waiting"],
  stored: ["ok", "In R2"],
  failed: ["danger", "Image failed"],
  rejected: ["muted", "Image not permitted"],
  superseded: ["muted", "Replaced"],
};
export const RECOMMENDATION_TONE: Record<string, Tone> = {
  safe_batch: "ok",
  review: "info",
  clinical_review: "warn",
  regulator_review: "warn",
  fix_source: "danger",
  duplicate: "warn",
  incomplete: "warn",
  blocked: "danger",
};

/** Hosts the site's image proxy is configured for (next.config.ts). Anything else is shown as a
 * link only, because next/image refuses unknown hosts. */
const R2_HOST = process.env.NEXT_PUBLIC_R2_PUBLIC_HOST ?? "";
export function canProxy(url: string): boolean {
  try {
    const h = new URL(url).hostname;
    return (
      h === "upload.wikimedia.org" || h === "thumb.wikimedia.org" || (!!R2_HOST && h === R2_HOST)
    );
  } catch {
    return false;
  }
}

/** Thumbnail that opens a larger preview in place. */
export function ImageThumb({ src, alt }: { src: string; alt: string }) {
  const [big, setBig] = useState(false);
  if (!canProxy(src))
    return (
      <div className="flex size-24 items-center justify-center rounded border border-border p-1 text-center text-xs text-muted">
        Preview unavailable for this host
      </div>
    );
  return (
    <button
      type="button"
      onClick={() => setBig((b) => !b)}
      aria-expanded={big}
      aria-label={big ? `Shrink preview of ${alt}` : `Enlarge preview of ${alt}`}
      className={`block overflow-hidden rounded border border-border bg-black/5 ${big ? "w-full max-w-md" : "size-24"}`}
    >
      <Image
        src={src}
        alt={alt}
        width={big ? 640 : 96}
        height={big ? 480 : 96}
        className={`h-full w-full ${big ? "object-contain" : "object-cover"}`}
      />
    </button>
  );
}

export function ProgressBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className="h-2 w-full overflow-hidden rounded bg-black/10"
    >
      <div className="h-full bg-primary transition-[width]" style={{ width: `${pct}%` }} />
    </div>
  );
}
