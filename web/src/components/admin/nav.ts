import {
  AlertTriangle,
  Briefcase,
  Bot,
  Database,
  Download,
  LayoutDashboard,
  ListChecks,
  MessageSquareWarning,
  ScrollText,
  Tag,
  Zap,
  type LucideIcon,
} from "lucide-react";

export type SectionKey =
  | "overview"
  | "queue"
  | "listings"
  | "prices"
  | "reports"
  | "imports"
  | "sources"
  | "automation"
  | "ai"
  | "errors"
  | "audit";

export interface NavItem {
  key: SectionKey;
  label: string;
  icon: LucideIcon;
  /** Roles allowed to see it; "all" = any staff. */
  access: "all" | "moderator" | "admin";
}
export interface NavGroup {
  label: string;
  items: NavItem[];
}

/** Every item maps to a feature that already exists; nothing here is a placeholder. */
export const NAV: NavGroup[] = [
  {
    label: "Overview",
    items: [{ key: "overview", label: "Dashboard", icon: LayoutDashboard, access: "all" }],
  },
  {
    label: "Review & moderation",
    items: [
      { key: "queue", label: "Review queue", icon: ListChecks, access: "all" },
      { key: "listings", label: "Jobs & scholarships", icon: Briefcase, access: "moderator" },
      { key: "prices", label: "Price submissions", icon: Tag, access: "moderator" },
      {
        key: "reports",
        label: "Question reports",
        icon: MessageSquareWarning,
        access: "moderator",
      },
    ],
  },
  {
    label: "Data & sources",
    items: [
      { key: "imports", label: "Imports", icon: Download, access: "all" },
      { key: "sources", label: "Source registry", icon: Database, access: "admin" },
    ],
  },
  {
    label: "AI & automation",
    items: [
      { key: "automation", label: "Automation & sources", icon: Zap, access: "all" },
      { key: "ai", label: "AI providers & usage", icon: Bot, access: "admin" },
    ],
  },
  {
    label: "Operations",
    items: [
      { key: "errors", label: "Errors", icon: AlertTriangle, access: "all" },
      { key: "audit", label: "Audit log", icon: ScrollText, access: "admin" },
    ],
  },
];

export function canSee(item: NavItem, role: string): boolean {
  if (item.access === "all") return true;
  if (item.access === "admin") return role === "admin";
  return role === "moderator" || role === "admin";
}

/** Old `?tab=` URLs and bookmarks keep working. */
export function parseSection(raw: string | null, role: string): SectionKey {
  const all = NAV.flatMap((g) => g.items);
  const hit = all.find((i) => i.key === raw);
  return hit && canSee(hit, role) ? hit.key : "overview";
}
