"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

// Phone navigation overflow: a fifth tab opens a bottom sheet with the rest of the site.
type Groups = { title: string; links: { href: string; label: string }[] }[];
const SHEET_ID = "more-sheet";

/** The "More" tab. Lives in the tab bar; the sheet it opens is rendered outside the nav. */
export function MoreButton({ groups }: { groups: Groups }) {
  const pathname = usePathname();
  const inMore = groups.some((g) =>
    g.links.some(
      (l) =>
        !["/search", "/calculators", "/study"].includes(l.href) &&
        (pathname === l.href || pathname.startsWith(`${l.href}/`)),
    ),
  );

  return (
    <button
      type="button"
      onClick={() => (document.getElementById(SHEET_ID) as HTMLDialogElement | null)?.showModal()}
      aria-haspopup="dialog"
      aria-controls={SHEET_ID}
      className={`flex min-h-14 min-w-11 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium ${
        inMore ? "text-primary" : "text-muted"
      }`}
    >
      <Menu size={20} strokeWidth={1.5} aria-hidden="true" />
      <span>More</span>
    </button>
  );
}

/**
 * Native <dialog> gives the focus trap, Escape and the backdrop; the slide-up lives in CSS
 * (`.sheet`) and is reduced to a fade for visitors who ask for less motion.
 */
export function MoreSheet({ groups }: { groups: Groups }) {
  const ref = useRef<HTMLDialogElement>(null);
  const pathname = usePathname();
  // Close after navigating.
  useEffect(() => {
    ref.current?.close();
  }, [pathname]);
  return (
    <dialog
      id={SHEET_ID}
      ref={ref}
      aria-label="More pages"
      onClick={(e) => {
        if (e.target === e.currentTarget) ref.current?.close();
      }}
      className="sheet fixed inset-x-0 bottom-0 top-auto m-0 max-h-[85dvh] w-full max-w-none overflow-y-auto rounded-t-[var(--radius-xl)] border-t border-border bg-surface p-0 text-text backdrop:bg-black/40"
    >
      <div className="sticky top-0 flex items-center justify-between border-b border-border bg-surface px-4 py-2">
        <p className="text-base font-medium">More</p>
        <button
          type="button"
          onClick={() => ref.current?.close()}
          aria-label="Close"
          className="-mr-2 inline-flex size-11 items-center justify-center rounded-md text-muted hover:bg-surface-2"
        >
          <X size={20} strokeWidth={1.5} aria-hidden="true" />
        </button>
      </div>
      <div className="space-y-6 px-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))] pt-4">
        {groups.map((g) => (
          <section key={g.title}>
            <h2 className="text-sm text-muted">{g.title}</h2>
            <ul className="mt-2 grid grid-cols-2 gap-2">
              {g.links.map((l) => {
                const active = pathname === l.href || pathname.startsWith(`${l.href}/`);
                return (
                  <li key={l.href}>
                    <Link
                      href={l.href}
                      aria-current={active ? "page" : undefined}
                      className={`neo flex min-h-12 items-center rounded-[var(--radius-md)] px-3 text-sm ${
                        active ? "border-primary text-primary" : ""
                      }`}
                    >
                      {l.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </dialog>
  );
}
