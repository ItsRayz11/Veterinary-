"use client";

import { useEffect, useRef, type ReactNode } from "react";

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
      aria-labelledby="modal-title"
      className="m-auto w-[min(32rem,92vw)] rounded-md border border-border bg-surface p-4 text-text backdrop:bg-black/50"
    >
      <h2 id="modal-title" className="mb-2 text-base font-semibold">
        {title}
      </h2>
      {children}
    </dialog>
  );
}
