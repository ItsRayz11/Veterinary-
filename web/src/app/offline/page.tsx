import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Offline", robots: { index: false } };

export default function OfflinePage() {
  return (
    <main className="mx-auto max-w-md space-y-3 pt-8">
      <h1 className="text-xl font-semibold">You are offline</h1>
      <p className="text-sm text-muted">
        This page is not saved on your device. Pages you opened before, and the calculators, still
        work without a connection. Reference data, prices, study content and your account need a
        connection.
      </p>
      <p className="text-sm">
        <Link className="text-primary underline" href="/calculators">
          Open the calculators
        </Link>
      </p>
    </main>
  );
}
