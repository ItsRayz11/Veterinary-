"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { CircleHelp } from "lucide-react";

/**
 * Small "(?)" button that opens an accessible popover with the longer explanation.
 * Button + disclosure pattern: aria-expanded, Escape and outside click close it, focus stays on the
 * button. Never put the only copy of a clinically critical warning in here.
 */
export function HelpTip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onDown = (e: Event) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  return (
    <span ref={root} className="relative inline-block align-middle">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        aria-label={label}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex min-h-6 min-w-6 items-center justify-center rounded-full text-muted hover:text-text focus-visible:outline-2"
      >
        <CircleHelp size={18} aria-hidden="true" />
      </button>
      {open && (
        <span
          id={id}
          role="region"
          aria-label={label}
          className="card absolute left-0 top-full z-30 mt-2 block w-[min(20rem,85vw)] p-3 text-sm font-normal leading-relaxed text-text shadow-lg"
        >
          {children}
        </span>
      )}
    </span>
  );
}
