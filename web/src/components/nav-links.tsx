"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface NavItem {
  href: string;
  label: string;
}

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export function NavLinks({ items, variant }: { items: NavItem[]; variant: "top" | "bottom" }) {
  const pathname = usePathname();
  return (
    <>
      {items.map((n) => {
        const active = isActive(pathname, n.href);
        const cls =
          variant === "top"
            ? `rounded-full px-3 py-1.5 transition-colors ${
                active
                  ? "bg-primary text-primary-fg"
                  : "text-muted hover:bg-surface-2 hover:text-text"
              }`
            : `min-w-0 flex-1 truncate px-0.5 py-3 text-center text-[11px] font-medium ${
                active ? "text-primary" : "text-muted"
              }`;
        return (
          <Link
            key={n.href}
            href={n.href}
            aria-current={active ? "page" : undefined}
            className={cls}
          >
            {n.label}
          </Link>
        );
      })}
    </>
  );
}
