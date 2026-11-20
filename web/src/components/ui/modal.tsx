"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

/** Native <dialog>: focus trap, Escape to close and backdrop come from the browser. */
export function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => {
        // Click on the backdrop (outside the dialog box) closes it.
        if (e.target === e.currentTarget) onClose();
      }}
      aria-labelledby={titleId}
      className="m-auto max-h-[92vh] w-[min(32rem,92vw)] overflow-y-auto card p-4 text-text backdrop:bg-black/50"
    >
      <div className="sticky top-0 z-10 -mx-4 -mt-4 mb-2 flex items-start justify-between gap-2 bg-surface px-4 pt-4 pb-2">
        <h2 id={titleId} className="text-base font-semibold">
          {title}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="-mr-2 -mt-2 inline-flex size-11 shrink-0 items-center justify-center rounded-lg text-xl leading-none text-muted hover:bg-surface-2"
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  );
}
