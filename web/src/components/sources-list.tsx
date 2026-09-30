import type { SourceRef } from "@/lib/api";
import { EmptyState } from "@/components/ui/primitives";

export function SourcesList({ sources }: { sources: SourceRef[] }) {
  if (!sources.length)
    return (
      <EmptyState title="No sources linked">
        Verified information is currently unavailable for this section.
      </EmptyState>
    );
  return (
    <ol className="list-decimal space-y-1 pl-5 text-sm">
      {sources.map((s) => (
        <li key={`${s.id}-${s.locator}`}>
          {s.url ? (
            <a
              href={s.url}
              rel="noopener noreferrer"
              target="_blank"
              className="text-primary underline"
            >
              {s.title}
            </a>
          ) : (
            s.title
          )}
          {s.publisher && <span className="text-muted">, {s.publisher}</span>}
          {s.publication_date && (
            <span className="text-muted"> ({s.publication_date.slice(0, 4)})</span>
          )}
          {s.doi && <span className="text-muted">, DOI {s.doi}</span>}
          {s.locator && <span className="text-muted">, {s.locator}</span>}
        </li>
      ))}
    </ol>
  );
}
