"use client";

import {
  ChevronRight,
  ExternalLink,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { apiFetch } from "@/lib/client-api";
import { STAFF_ROLES, useUser } from "@/lib/use-user";
import { AiTab } from "./ai-tab";
import { CatalogsTab } from "./catalogs-tab";
import { ContentTab } from "./content-tab";
import { MarketTab } from "./market-tab";
import { AutomationTab } from "./automation-tab";
import { ErrorsTab } from "./errors-tab";
import { ImportsTab } from "./imports-tab";
import { ListingsTab } from "./listings-tab";
import { NAV, canSee, parseSection, type SectionKey } from "./nav";
import { Overview } from "./overview";
import { SourcesTab } from "./sources-tab";
import { AuditLogTab, PricesTab, QuestionReportsTab, ReviewQueueTab } from "./tabs";

export interface Summary {
  review_queue: Record<string, number>;
  price_submissions_pending: number;
  question_reports_open: number;
  listings_pending?: number;
  articles_in_review?: number;
  articles_published?: number;
  prices_recent_7d?: number;
  catalogs_pending?: number;
  suppliers_pending?: number;
  offers_pending?: number;
  leads_new?: number;
  ai_month_calls?: number;
  ai_month_cost_usd?: string;
  admin_url?: string; // from the API, so a private ADMIN_URL never ships in the public bundle
  role: string;
  can_approve_clinical: boolean;
}

export function AdminPanel() {
  const user = useUser();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [tab, setTabState] = useState<SectionKey>("overview");
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [find, setFind] = useState("");
  const [version, setVersion] = useState(0);
  const staff = !!user && STAFF_ROLES.has(user.role);
  const role = user?.role ?? "";

  useEffect(() => {
    if (!staff) return;
    let live = true;
    apiFetch<Summary>("/staff/summary").then((s) => live && setSummary(s));
    return () => {
      live = false;
    };
  }, [staff, version]);

  // Deep links: ?section=queue (the old ?tab=queue still works); back/forward move between sections.
  useEffect(() => {
    if (!role) return;
    const read = () => {
      const q = new URLSearchParams(window.location.search);
      setTabState(parseSection(q.get("section") ?? q.get("tab"), role));
    };
    read();
    try {
      setCollapsed(localStorage.getItem("admin-nav-collapsed") === "1");
    } catch {
      /* storage unavailable: default layout */
    }
    window.addEventListener("popstate", read);
    return () => window.removeEventListener("popstate", read);
  }, [role]);

  if (user === undefined) return <Skeleton className="h-32 w-full" />;
  if (staff && user.mfa_required && !user.mfa_verified)
    return (
      <>
        <h1 className="sr-only">Review panel</h1>
        <Alert tone="warn" title="Two-factor authentication needed">
          Staff must use two-factor authentication.{" "}
          {user.mfa_enabled ? (
            "Sign out and sign in again, then enter your code."
          ) : (
            <Link href="/account" className="underline">
              Set it up in your account
            </Link>
          )}
          .
        </Alert>
      </>
    );
  if (!staff)
    return (
      <>
        <h1 className="sr-only">Review panel</h1>
        <Alert tone="warn" title="Staff only">
          This panel is for reviewers, editors, moderators and admins.{" "}
          {!user && (
            <Link href="/login?next=/admin-panel" className="underline">
              Sign in
            </Link>
          )}
        </Alert>
      </>
    );

  const isModerator = user.role === "moderator" || user.role === "admin";
  const queueTotal = summary ? Object.values(summary.review_queue).reduce((a, b) => a + b, 0) : 0;
  const counts: Partial<Record<SectionKey, number | undefined>> = {
    queue: queueTotal,
    listings: summary?.listings_pending,
    prices: summary?.price_submissions_pending,
    reports: summary?.question_reports_open,
    content: summary?.articles_in_review,
    market: summary?.offers_pending,
    catalogs: (summary?.catalogs_pending ?? 0) + (summary?.suppliers_pending ?? 0) || undefined,
  };
  const refresh = () => setVersion((v) => v + 1);
  const setTab = (k: SectionKey) => {
    setTabState(k);
    setDrawer(false);
    const u = new URL(window.location.href);
    u.searchParams.delete("tab");
    u.searchParams.set("section", k);
    window.history.pushState(null, "", u);
    window.scrollTo({ top: 0 });
  };
  const toggleCollapsed = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem("admin-nav-collapsed", c ? "0" : "1");
      } catch {
        /* ignore */
      }
      return !c;
    });
  };
  const needle = find.trim().toLowerCase();
  const groups = NAV.map((g) => ({
    ...g,
    items: g.items.filter(
      (i) =>
        canSee(i, user.role) && (!needle || `${i.label} ${g.label}`.toLowerCase().includes(needle)),
    ),
  })).filter((g) => g.items.length);
  const current = NAV.flatMap((g) => g.items.map((i) => ({ g, i }))).find((x) => x.i.key === tab);
  const djangoAdmin = `${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}${summary?.admin_url ?? "/admin/"}`;

  const nav = (rail: boolean) => (
    <nav aria-label="Admin sections" className="flex h-full flex-col gap-3 overflow-y-auto p-2">
      {!rail && (
        <label className="relative block">
          <span className="sr-only">Find a section</span>
          <Search
            aria-hidden
            className="pointer-events-none absolute left-2 top-3 size-4 text-muted"
          />
          <input
            type="search"
            value={find}
            onChange={(e) => setFind(e.target.value)}
            placeholder="Find a section"
            maxLength={40}
            className="min-h-10 w-full rounded-md border border-border bg-transparent pl-8 pr-2 text-sm"
          />
        </label>
      )}
      {groups.map((g) => (
        <div key={g.label}>
          {!rail && (
            <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
              {g.label}
            </p>
          )}
          <ul className="space-y-0.5">
            {g.items.map((i) => {
              const Icon = i.icon;
              const n = counts[i.key];
              const active = tab === i.key;
              return (
                <li key={i.key}>
                  <button
                    type="button"
                    onClick={() => setTab(i.key)}
                    aria-current={active ? "page" : undefined}
                    title={rail ? i.label : undefined}
                    className={`flex min-h-10 w-full items-center gap-2 rounded-md px-2 text-left text-sm ${rail ? "justify-center" : ""} ${active ? "bg-primary/10 font-medium text-primary" : "hover:bg-black/5"}`}
                  >
                    <Icon aria-hidden className="size-4 shrink-0" />
                    {rail ? (
                      <span className="sr-only">
                        {i.label}
                        {n ? `, ${n} waiting` : ""}
                      </span>
                    ) : (
                      <span className="min-w-0 flex-1 truncate">{i.label}</span>
                    )}
                    {!rail && n ? (
                      <span className="rounded-full bg-primary/15 px-1.5 text-xs">
                        {n.toLocaleString()}
                      </span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {!groups.length && <p className="px-2 text-sm text-muted">No section matches.</p>}
      <div className="mt-auto border-t border-border pt-2">
        <a
          href={djangoAdmin}
          title={rail ? "Django admin" : undefined}
          className={`flex min-h-10 items-center gap-2 rounded-md px-2 text-sm hover:bg-black/5 ${rail ? "justify-center" : ""}`}
        >
          <ExternalLink aria-hidden className="size-4 shrink-0" />
          {rail ? <span className="sr-only">Django admin</span> : "Django admin (advanced)"}
        </a>
      </div>
    </nav>
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-md border border-border lg:hidden"
          aria-label="Open admin menu"
          aria-expanded={drawer}
          onClick={() => setDrawer(true)}
        >
          <Menu aria-hidden className="size-5" />
        </button>
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">Review panel</h1>
          <p className="text-xs text-muted">
            {user.username} ({user.role})
            {summary &&
              !summary.can_approve_clinical &&
              " · clinical sign-off needs a veterinarian reviewer"}
          </p>
        </div>
      </div>

      <div className="flex items-start gap-4">
        <aside
          className={`sticky top-2 hidden max-h-[calc(100vh-1rem)] shrink-0 flex-col overflow-hidden rounded-lg border border-border bg-surface lg:flex ${collapsed ? "w-14" : "w-60"}`}
        >
          <div className="min-h-0 flex-1">{nav(collapsed)}</div>
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex min-h-10 w-full items-center justify-center border-t border-border text-muted hover:bg-black/5"
          >
            {collapsed ? (
              <PanelLeftOpen aria-hidden className="size-4" />
            ) : (
              <PanelLeftClose aria-hidden className="size-4" />
            )}
          </button>
        </aside>

        {drawer && (
          <div
            className="fixed inset-0 z-50 lg:hidden"
            role="dialog"
            aria-modal="true"
            aria-label="Admin menu"
          >
            <button
              type="button"
              aria-label="Close admin menu"
              className="absolute inset-0 bg-black/40"
              onClick={() => setDrawer(false)}
            />
            <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-surface shadow-xl">
              <button
                type="button"
                aria-label="Close admin menu"
                className="absolute right-1 top-1 inline-flex min-h-10 min-w-10 items-center justify-center"
                onClick={() => setDrawer(false)}
              >
                <X aria-hidden className="size-5" />
              </button>
              <div className="h-full pt-10">{nav(false)}</div>
            </div>
          </div>
        )}

        <main className="min-w-0 flex-1 space-y-3">
          <nav
            aria-label="Breadcrumb"
            className="flex flex-wrap items-center gap-1 text-xs text-muted"
          >
            <span>Admin</span>
            {current && tab !== "overview" && (
              <>
                <ChevronRight aria-hidden className="size-3" />
                <span>{current.g.label}</span>
                <ChevronRight aria-hidden className="size-3" />
                <span aria-current="page" className="text-foreground">
                  {current.i.label}
                </span>
              </>
            )}
          </nav>
          <h2 className="text-lg font-semibold">{current?.i.label ?? "Dashboard"}</h2>
          <div>
            {tab === "overview" && (
              <Overview summary={summary} isModerator={isModerator} go={setTab} />
            )}
            {tab === "queue" && (
              <ReviewQueueTab counts={summary?.review_queue ?? {}} onChanged={refresh} />
            )}
            {tab === "imports" && <ImportsTab onChanged={refresh} />}
            {tab === "listings" && isModerator && <ListingsTab onChanged={refresh} />}
            {tab === "prices" && isModerator && <PricesTab onChanged={refresh} />}
            {tab === "reports" && isModerator && <QuestionReportsTab onChanged={refresh} />}
            {tab === "sources" && user.role === "admin" && <SourcesTab />}
            {tab === "content" && <ContentTab />}
            {tab === "market" && isModerator && <MarketTab admin={user.role === "admin"} />}
            {tab === "catalogs" && isModerator && <CatalogsTab admin={user.role === "admin"} />}
            {tab === "ai" && user.role === "admin" && <AiTab />}
            {tab === "automation" && <AutomationTab />}
            {tab === "errors" && <ErrorsTab />}
            {tab === "audit" && user.role === "admin" && <AuditLogTab />}
          </div>
        </main>
      </div>
    </div>
  );
}
