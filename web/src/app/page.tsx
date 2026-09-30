import { StatusBadge } from "@/components/ui/status-badge";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8">
      <h1 className="text-xl font-semibold">Veterinary reference</h1>
      <p className="mt-1 text-sm text-muted">
        Foundation build. No clinical data is published yet.
      </p>
      <div className="mt-4">
        <StatusBadge status="development" />
      </div>
    </main>
  );
}
