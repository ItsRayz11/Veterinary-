"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { apiFetch } from "@/lib/client-api";
import { STAFF_ROLES, useUser } from "@/lib/use-user";
import { AuditLogTab, PricesTab, QuestionReportsTab, ReviewQueueTab } from "./tabs";

export interface Summary {
  review_queue: Record<string, number>;
  price_submissions_pending: number;
  question_reports_open: number;
  role: string;
  can_approve_clinical: boolean;
}

type TabKey = "queue" | "prices" | "reports" | "audit";

export function AdminPanel() {
  const user = useUser();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [tab, setTab] = useState<TabKey>("queue");
  const [version, setVersion] = useState(0);
  const staff = !!user && STAFF_ROLES.has(user.role);

  useEffect(() => {
    if (!staff) return;
    let live = true;
    apiFetch<Summary>("/staff/summary").then((s) => live && setSummary(s));
    return () => {
      live = false;
    };
  }, [staff, version]);

  if (user === undefined) return <Skeleton className="h-32 w-full" />;
  if (!staff)
    return (
      <Alert tone="warn" title="Staff only">
        This panel is for reviewers, editors, moderators and admins.{" "}
        {!user && (
          <Link href="/login?next=/admin-panel" className="underline">
            Sign in
          </Link>
        )}
      </Alert>
    );

  const queueTotal = summary ? Object.values(summary.review_queue).reduce((a, b) => a + b, 0) : 0;
  const isModerator = user.role === "moderator" || user.role === "admin";
  const tabs: { key: TabKey; label: string; count?: number; show: boolean }[] = [
    { key: "queue", label: "Review queue", count: queueTotal, show: true },
    {
      key: "prices",
      label: "Price submissions",
      count: summary?.price_submissions_pending,
      show: isModerator,
    },
    {
      key: "reports",
      label: "Question reports",
      count: summary?.question_reports_open,
      show: isModerator,
    },
    { key: "audit", label: "Audit log", show: user.role === "admin" },
  ];
  const refresh = () => setVersion((v) => v + 1);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Review panel</h1>
      <p className="text-sm text-muted">
        Signed in as {user.username} ({user.role}).{" "}
        {summary && !summary.can_approve_clinical && (
          <>
            You can move records through the queue but only veterinarian reviewers and admins can
            sign off clinical data.{" "}
          </>
        )}
        Full data editing is in the{" "}
        <a className="text-primary underline" href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}/admin/`}>
          Django admin
        </a>
        .
      </p>
      <div
        role="tablist"
        aria-label="Review sections"
        className="flex flex-wrap gap-2 border-b border-border"
      >
        {tabs
          .filter((t) => t.show)
          .map((t) => (
            <button
              key={t.key}
              role="tab"
              type="button"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={`min-h-11 px-3 text-sm ${tab === t.key ? "border-b-2 border-primary font-medium" : "text-muted"}`}
            >
              {t.label}
              {t.count ? ` (${t.count})` : ""}
            </button>
          ))}
      </div>
      <div role="tabpanel">
        {tab === "queue" && (
          <ReviewQueueTab counts={summary?.review_queue ?? {}} onChanged={refresh} />
        )}
        {tab === "prices" && isModerator && <PricesTab onChanged={refresh} />}
        {tab === "reports" && isModerator && <QuestionReportsTab onChanged={refresh} />}
        {tab === "audit" && user.role === "admin" && <AuditLogTab />}
      </div>
    </div>
  );
}
