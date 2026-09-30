"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "./client-api";

export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  mfa_enabled?: boolean;
  mfa_required?: boolean; // staff in production
  mfa_verified?: boolean; // this session has passed the second factor
}

/** Roles that may open the staff review panel (the API still enforces each action's own permission). */
export const STAFF_ROLES = new Set(["reviewer", "vet_reviewer", "editor", "moderator", "admin"]);

/** undefined = still loading, null = signed out. Refreshes when auth changes anywhere on the page. */
export function useUser(): User | null | undefined {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    const load = () =>
      apiFetch<User>("/auth/me")
        .then((u) => live && setUser(u))
        .catch(() => live && setUser(null));
    load();
    window.addEventListener("auth-changed", load);
    return () => {
      live = false;
      window.removeEventListener("auth-changed", load);
    };
  }, []);
  return user;
}

export const notifyAuthChanged = () => window.dispatchEvent(new Event("auth-changed"));
