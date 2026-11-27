"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CATEGORIES, type CategoryName } from "@/components/ui/icons";

export interface NavItem {
  href: string;
  label: string;
  icon?: CategoryName;
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
        const Icon = n.icon ? CATEGORIES[n.icon].icon : null;
        // Desktop: labels only, the active page is a quiet surface step. Phones: icon over label.
        const cls =
          variant === "top"
            ? `inline-flex h-9 items-center rounded-[var(--radius-md)] px-3 transition-colors ${
                active
                  ? "bg-surface-2 font-medium text-text"
                  : "text-text-2 hover:bg-surface-2 hover:text-text"
              }`
            : `flex min-h-14 min-w-11 flex-1 flex-col items-center justify-center gap-1 text-center text-[11px] font-medium ${
                active ? "text-primary" : "text-muted"
              }`;
        return (
          <Link
            key={n.href}
            href={n.href}
            aria-current={active ? "page" : undefined}
            className={cls}
          >
            {Icon && variant === "bottom" && (
              <Icon size={20} strokeWidth={1.5} aria-hidden="true" />
            )}
            <span className="max-w-full truncate">{n.label}</span>
          </Link>
        );
      })}
    </>
  );
}
