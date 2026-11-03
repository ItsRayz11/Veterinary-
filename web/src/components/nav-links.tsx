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
        const cls =
          variant === "top"
            ? `inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors ${
                active
                  ? "bg-primary text-primary-fg"
                  : "text-muted hover:bg-surface-2 hover:text-text"
              }`
            : `flex min-w-0 flex-1 flex-col items-center gap-0.5 px-0.5 py-2 text-center text-[11px] font-medium ${
                active ? "text-primary" : "text-muted"
              }`;
        return (
          <Link
            key={n.href}
            href={n.href}
            aria-current={active ? "page" : undefined}
            className={cls}
          >
            {Icon && (
              <Icon size={variant === "top" ? 15 : 20} strokeWidth={1.75} aria-hidden="true" />
            )}
            <span className="max-w-full truncate">{n.label}</span>
          </Link>
        );
      })}
    </>
  );
}
