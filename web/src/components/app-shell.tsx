import Link from "next/link";
import type { ReactNode } from "react";
import { AuthMenu } from "@/components/auth-menu";
import { NavLinks } from "@/components/nav-links";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Search" },
  { href: "/calculators", label: "Calculators" },
  { href: "/study", label: "Study" },
  { href: "/jobs", label: "Jobs" },
  { href: "/scholarships", label: "Scholarships" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface focus:p-2"
      >
        Skip to content
      </a>
      <header className="glass sticky top-0 z-30 border-x-0 border-t-0">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-4">
          <Link href="/" className="text-lg font-semibold tracking-tight text-primary">
            VetRef
          </Link>
          <nav aria-label="Primary" className="hidden gap-1 text-sm sm:flex">
            <NavLinks items={NAV} variant="top" />
          </nav>
          <div className="ml-auto">
            <AuthMenu />
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 pb-24 pt-4 sm:pb-8">
        {children}
      </main>
      <footer className="hidden border-t border-border py-4 text-center text-xs text-muted sm:block">
        Clinical reference for licensed veterinary professionals. Does not replace clinical
        judgement or the product label.
      </footer>
      <nav
        aria-label="Mobile"
        className="glass fixed inset-x-0 bottom-0 z-30 flex border-x-0 border-b-0 pb-[env(safe-area-inset-bottom)] sm:hidden"
      >
        <NavLinks items={NAV.filter((n) => n.href !== "/")} variant="bottom" />
      </nav>
    </>
  );
}
