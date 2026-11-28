import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { AuthMenu } from "@/components/auth-menu";
import { MoreButton, MoreSheet } from "@/components/mobile-more";
import { NavLinks, type NavItem } from "@/components/nav-links";
import { NavigationProgress } from "@/components/navigation-progress";
import { PublicChrome } from "@/components/public-chrome";
import { Logo } from "@/components/ui/logo";

const NAV: NavItem[] = [
  { icon: "home", href: "/", label: "Home" },
  { icon: "search", href: "/search", label: "Search" },
  { icon: "calculators", href: "/calculators", label: "Calculators" },
  { icon: "study", href: "/study", label: "Study" },
  { icon: "universities", href: "/universities", label: "Universities" },
  { icon: "jobs", href: "/jobs", label: "Jobs" },
  { icon: "scholarships", href: "/scholarships", label: "Scholarships" },
];

/** Phones get four tabs plus "More": a bottom bar holds five targets at most. */
const TABS = NAV.filter((n) => ["/", "/search", "/calculators", "/study"].includes(n.href));

/** Everything else, grouped as people look for it. Shared by the footer and the "More" sheet. */
export const SITE_MAP: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Reference",
    links: [
      { href: "/search", label: "Search" },
      { href: "/species", label: "Species" },
      { href: "/classes", label: "Drug classes" },
      { href: "/countries", label: "Countries" },
      { href: "/interactions", label: "Interactions" },
      { href: "/ask", label: "Ask the reference" },
    ],
  },
  {
    title: "Tools and study",
    links: [
      { href: "/calculators", label: "Calculators" },
      { href: "/study", label: "Study" },
      { href: "/blog", label: "Articles" },
      { href: "/catalogs-3d", label: "3D catalogs" },
    ],
  },
  {
    title: "Careers",
    links: [
      { href: "/universities", label: "Universities" },
      { href: "/jobs", label: "Jobs" },
      { href: "/scholarships", label: "Scholarships" },
    ],
  },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <>
      <Suspense fallback={null}>
        <NavigationProgress />
      </Suspense>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface focus:p-2"
      >
        Skip to content
      </a>
      <PublicChrome>
        <header className="chrome-bar sticky top-0 z-30 border-b">
          <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
            <Link href="/" aria-label="VetRef home" className="-ml-1 rounded-md p-1">
              <Logo />
            </Link>
            <nav aria-label="Primary" className="hidden items-center gap-1 text-sm lg:flex">
              <NavLinks items={NAV} variant="top" />
            </nav>
            <div className="ml-auto">
              <AuthMenu />
            </div>
          </div>
        </header>
      </PublicChrome>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-12 pt-6 sm:px-6 lg:pb-16">
        {children}
      </main>
      <PublicChrome>
        <footer className="border-t border-border bg-surface pb-24 lg:pb-8">
          <div className="mx-auto grid max-w-6xl gap-8 px-4 pt-10 sm:px-6 md:grid-cols-[1.4fr_repeat(3,1fr)]">
            <div className="space-y-3">
              <Logo />
              <p className="max-w-xs text-sm text-muted">
                Clinical reference for licensed veterinary professionals. It does not replace
                clinical judgement or the product label.
              </p>
            </div>
            {SITE_MAP.map((g) => (
              <nav key={g.title} aria-label={g.title}>
                <h2 className="text-sm font-medium text-text">{g.title}</h2>
                <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm md:grid-cols-1">
                  {g.links.map((l) => (
                    <li key={l.href}>
                      <Link
                        href={l.href}
                        className="inline-flex min-h-8 items-center text-text-2 hover:text-primary"
                      >
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
          <div className="mx-auto mt-8 max-w-6xl px-4 sm:px-6">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-4 text-xs text-muted">
              <span className="inline-flex items-center gap-1.5">
                <span className="review-mark text-ok" aria-hidden="true" />
                Reviewed
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="review-mark text-warn" data-reviewed="false" aria-hidden="true" />
                Not yet reviewed
              </span>
              <Link href="/credits" className="ml-auto underline-offset-2 hover:underline">
                Image and data credits
              </Link>
            </div>
          </div>
        </footer>
      </PublicChrome>
      <PublicChrome>
        <nav
          aria-label="Mobile"
          className="chrome-bar fixed inset-x-0 bottom-0 z-30 flex border-t pb-[env(safe-area-inset-bottom)] lg:hidden"
        >
          <NavLinks items={TABS} variant="bottom" />
          <MoreButton groups={SITE_MAP} />
        </nav>
        <MoreSheet groups={SITE_MAP} />
      </PublicChrome>
    </>
  );
}
