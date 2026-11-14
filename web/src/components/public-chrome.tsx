"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/** Hides the public-site chrome (header, footer, mobile tabs) on the staff admin panel. */
export function PublicChrome({ children }: { children: ReactNode }) {
  const path = usePathname();
  if (path === "/admin-panel" || path?.startsWith("/admin-panel/")) return null;
  return <>{children}</>;
}
