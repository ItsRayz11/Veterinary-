# Performance notes (measured 2026-11-04 from Mumbai to Vercel iad1 / Neon us-east-2)

| Request | Time to first byte |
|---|---|
| API health (warm) | 0.9-1.7 s (about 0.6 s of that is network round trips from India) |
| API list endpoints (warm) | 0.9-1.4 s |
| Web pages (warm) | 0.6-1.1 s |
| First request after idle | 10 s seen on `/drug-classes/`; about 30 s seen on the first request after a deploy |

Both services are in the same region (iad1 / us-east-2), so region alignment is not the problem. The long first requests are cold starts: new Python function instance (importing Django and all apps), plus Neon waking an auto-suspended compute (compute auto-suspends after 5 minutes idle on this plan). Warm requests are well under 3 s.

Done: persistent, health-checked database connections per warm instance (`DB_CONN_MAX_AGE`, default 120 s); edge caching headers on public reads (already present); the 348 KB country page is now paginated.
Options needing a decision (cost): Neon "always on" compute (paid), Vercel Fluid compute / min instances, or a scheduled keep-warm request (artificial traffic). None enabled.
