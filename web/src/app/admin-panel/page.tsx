import type { Metadata } from "next";
import { AdminPanel } from "@/components/admin/admin-panel";

export const metadata: Metadata = { title: "Review panel", robots: { index: false } };

export default function AdminPanelPage() {
  return <AdminPanel />;
}
