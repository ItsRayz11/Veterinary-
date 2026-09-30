import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-xl space-y-2 pt-8">
      <h1 className="text-xl font-semibold">Not found</h1>
      <p className="text-sm text-muted">
        We could not find that record. It may not exist, or it has not been published yet.
      </p>
      <Link href="/search" className="text-primary underline">
        Search instead
      </Link>
    </main>
  );
}
