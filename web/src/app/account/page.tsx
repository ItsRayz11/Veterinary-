"use client";

import Link from "next/link";
import { Skeleton } from "@/components/ui/forms";
import { Alert } from "@/components/ui/primitives";
import { SecuritySettings } from "@/components/security-settings";
import { NotificationSettings } from "@/components/notification-settings";
import { STAFF_ROLES, useUser } from "@/lib/use-user";

export default function AccountPage() {
  const user = useUser();
  if (user === undefined) return <Skeleton className="h-24 w-full max-w-sm" />;
  if (!user)
    return (
      <>
        <h1 className="sr-only">Account</h1>
        <Alert tone="info">
          <Link href="/login?next=/account" className="underline">
            Sign in
          </Link>{" "}
          to view your account.
        </Alert>
      </>
    );
  return (
    <div className="max-w-md space-y-4">
      <h1 className="text-xl font-semibold">Account</h1>
      <dl className="space-y-1 text-sm">
        <div>
          <dt className="inline text-muted">Username: </dt>
          <dd className="inline">{user.username}</dd>
        </div>
        <div>
          <dt className="inline text-muted">Email: </dt>
          <dd className="inline">{user.email}</dd>
        </div>
        <div>
          <dt className="inline text-muted">Role: </dt>
          <dd className="inline">{user.role}</dd>
        </div>
      </dl>
      <SecuritySettings />
      <NotificationSettings />
      {STAFF_ROLES.has(user.role) && (
        <Link href="/admin-panel" className="text-primary underline">
          Open review panel
        </Link>
      )}
    </div>
  );
}
