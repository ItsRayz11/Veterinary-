import Link from "next/link";
import type { ReactNode } from "react";
import { AuthMenu } from "@/components/auth-menu";

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
      <header className="sticky top-0 z-30 border-b border-border bg-surface">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-4">
          <Link href="/" className="font-semibold text-primary">
            VetRef
          </Link>
          <nav aria-label="Primary" className="hidden gap-4 text-sm sm:flex">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className="text-muted hover:text-text">
                {n.label}
              </Link>
            ))}
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
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-surface sm:hidden"
      >
        {NAV.map((n) => (
          <Link key={n.href} href={n.href} className="flex-1 py-3 text-center text-sm">
            {n.label}
          </Link>
        ))}
      </nav>
    </>
  );
}
