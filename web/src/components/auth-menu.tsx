"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiSend } from "@/lib/client-api";
import { notifyAuthChanged, useUser } from "@/lib/use-user";

export function AuthMenu() {
  const user = useUser();
  const router = useRouter();
  if (user === undefined) return <span className="h-5 w-16" aria-hidden="true" />;
  if (!user)
    return (
      <div className="flex gap-1 whitespace-nowrap text-sm">
        <Link
          href="/login"
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md px-2 text-muted hover:text-text"
        >
          Sign in
        </Link>
        <Link
          href="/register"
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md px-2 font-medium text-primary"
        >
          Register
        </Link>
      </div>
    );
  return (
    <div className="flex items-center gap-1 text-sm">
      <Link
        href="/account"
        className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md px-2 text-muted hover:text-text"
      >
        {user.username}
      </Link>
      <button
        type="button"
        className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md px-2 text-muted hover:text-text"
        onClick={async () => {
          await apiSend("POST", "/auth/logout");
          notifyAuthChanged();
          router.push("/");
          router.refresh();
        }}
      >
        Sign out
      </button>
    </div>
  );
}
