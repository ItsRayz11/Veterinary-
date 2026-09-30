import type { PriceSeries, Prices } from "@/lib/api";
import { DataTable, td, th } from "@/components/ui/primitives";

const W = 160;
const H = 40;

function Sparkline({ s }: { s: PriceSeries }) {
  const values = s.points.map((p) => Number(p.amount));
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * (W - 8) + 4;
    const y = H - 4 - ((v - lo) / span) * (H - 8);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const first = s.points[0];
  const last = s.points[s.points.length - 1];
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width={W}
      height={H}
      role="img"
      aria-label={`Price from ${s.currency} ${first.amount} on ${first.date} to ${s.currency} ${last.amount} on ${last.date}`}
      className="text-primary"
    >
      <polyline points={pts.join(" ")} fill="none" stroke="currentColor" strokeWidth="2" />
      {pts.map((p, i) => (
        <circle key={i} cx={p.split(",")[0]} cy={p.split(",")[1]} r="2.5" fill="currentColor" />
      ))}
    </svg>
  );
}

const ARROW = { up: "▲", down: "▼", same: "■", none: "" } as const;

/** Trends and region comparison. Values are computed on the server with exact decimals. */
export function PriceTrends({ analytics }: { analytics: Prices["analytics"] }) {
  const series = analytics.series.filter((s) => s.points.length > 0);
  if (!series.length) return null;
  return (
    <div className="mt-4 space-y-4">
      <h3 className="font-semibold">Price history</h3>
      <ul className="space-y-3">
        {series.map((s, i) => {
          const where = [s.city, s.region, s.country].filter(Boolean).join(", ");
          return (
            <li key={i} className="rounded-md border border-border bg-surface p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium">
                    {s.pack} · {s.price_type.replaceAll("_", " ")}
                  </p>
                  <p className="text-xs text-muted">{where}</p>
                </div>
                <p className="text-right">
                  <span className="text-lg font-semibold">
                    {s.currency} {s.latest}
                  </span>
                  {s.change_percent !== null && (
                    <span
                      className={`block text-xs ${
                        s.direction === "up"
                          ? "text-danger"
                          : s.direction === "down"
                            ? "text-ok"
                            : "text-muted"
                      }`}
                    >
                      {ARROW[s.direction]} {s.direction === "up" ? "+" : ""}
                      {s.change_percent}% ({s.direction === "up" ? "+" : ""}
                      {s.change} since previous)
                    </span>
                  )}
                </p>
              </div>
              {s.points.length > 1 ? (
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <Sparkline s={s} />
                  <p className="text-xs text-muted">
                    Low {s.min} · High {s.max} · {s.points.length} observations
                  </p>
                </div>
              ) : (
                <p className="mt-1 text-xs text-muted">One observation so far; no trend yet.</p>
              )}
              <details className="mt-2 text-xs">
                <summary className="cursor-pointer">Data table</summary>
                <ul className="mt-1">
                  {s.points.map((p) => (
                    <li key={p.date}>
                      {p.date}: {s.currency} {p.amount}
                    </li>
                  ))}
                </ul>
              </details>
            </li>
          );
        })}
      </ul>
      {analytics.region_comparison.length > 0 && (
        <div className="space-y-2">
          <h3 className="font-semibold">Regional comparison</h3>
          {analytics.region_comparison.map((c, i) => (
            <DataTable
              key={i}
              caption={`${c.pack}, ${c.price_type.replaceAll("_", " ")} price by region (${c.currency})`}
            >
              <thead>
                <tr>
                  <th className={th}>
                    {c.pack} · {c.price_type.replaceAll("_", " ")}
                  </th>
                  <th className={th}>Latest price</th>
                  <th className={th}>Observed</th>
                </tr>
              </thead>
              <tbody>
                {c.regions.map((r) => (
                  <tr key={r.region}>
                    <th scope="row" className={td}>
                      {r.region}
                    </th>
                    <td className={td}>
                      {c.currency} {r.amount}
                    </td>
                    <td className={td}>{r.observed_on}</td>
                  </tr>
                ))}
                <tr>
                  <th scope="row" className={td}>
                    Spread (highest vs lowest)
                  </th>
                  <td className={td} colSpan={2}>
                    {c.currency} {c.spread} ({c.spread_percent}%)
                  </td>
                </tr>
              </tbody>
            </DataTable>
          ))}
        </div>
      )}
    </div>
  );
}
