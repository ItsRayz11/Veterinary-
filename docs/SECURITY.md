# Security

What is protected, how, and what is still open. Every control below names the test or check that covers it.

## Threats and controls

| Threat | Control | Verified by |
|---|---|---|
| Unreviewed or invented medical data shown as fact | Public querysets only return reviewed statuses; sign-off needs a source, a veterinarian reviewer and no self-approval; dev data can never be signed off (DB constraint); imports, feeds, jobs and prices all land unreviewed | `core`, `staff`, `ingestion`, `automation` tests |
| Privilege escalation via sign-up | Self-serve roles limited to registered/student/professional; staff endpoints check the role server-side on every call | `accounts`, `staff` tests; `test_hardening.py` |
| Credential stuffing / brute force | Per-IP throttle on login/register (10/min) using a cache shared across serverless instances (`CACHE_URL`) | auth throttle test; see gaps |
| CSRF | Django CSRF on all session-authenticated writes; token fetched from `/auth/csrf`; browser client refreshes it after login and retries once; CSRF cookie is HttpOnly | client + `test_hardening.py`; live login flow |
| XSS | React escaping; no `dangerouslySetInnerHTML`; user text stored as plain text; strict CSP (no remote scripts, `frame-ancestors 'none'`, `object-src 'none'`); external links use `rel="noopener noreferrer nofollow"` | `security-headers.test.ts`; headless Chrome load shows 0 CSP violations |
| SSRF via automation | Only staff-registered URLs are fetched; public IPs only, ports 80/443, every redirect re-validated, size/time caps, robots.txt honoured | `automation` tests (loopback, private, link-local, IPv6, file/ftp) |
| Hostile XML in feeds | `defusedxml`; entity bombs rejected | `automation` tests |
| LLM inventing or leaking data | Only reviewed records are retrieved; no record means no model call; JSON must cite provided records; every number must exist in them; failures show only the records; login + 20/hour limit; every exchange logged | 21 `assistant` tests incl. prompt injection |
| Spam / scam listings | Moderation before anything is public, no self-approval, 5-pending cap per user, 3 distinct reports send a listing back to review, original link required, automatic expiry | 7 `opportunities` tests |
| Abuse of the scheduler endpoint | `Bearer CRON_SECRET`, constant-time compare, disabled when unset | `automation` tests |
| Service worker leaking private pages | Deny list for API, account, admin, exams, flashcards, assistant and auth; only allow-listed public pages are cached | 16 sandbox tests + real-browser run with the network removed |
| Vulnerable dependencies | `pip-audit` and `npm audit` report nothing (2026-09-30) | re-run before each release |
| Secrets in git | `.env*` ignored; history scanned: no keys, tokens or connection strings | scan on 2026-09-30 |
| Weak transport | HTTPS redirect, secure cookies, HSTS (1 year) when `DEBUG=false`; `SECURE_PROXY_SSL_HEADER` for the Vercel proxy | `manage.py check --deploy` is clean |
| Oversized requests | `DATA_UPLOAD_MAX_MEMORY_SIZE` 3 MB, import file cap 2 MB / 5000 rows | `test_hardening.py`, `ingestion` tests |

## Known gaps (not fixed, on purpose or for lack of a decision)
- **No two-factor authentication** for staff. Reviewer, moderator and admin accounts are the crown jewels; add TOTP before onboarding real reviewers.
- **No per-account lockout**; only the per-IP throttle. Behind a shared NAT that can throttle honest users, and a distributed attacker is not slowed.
- **CSP allows `'unsafe-inline'`** for scripts and styles because Next.js emits inline bootstrap code. Moving to per-request nonces removes it.
- **DNS rebinding** between URL validation and connection in `safe_http` (documented there; only staff-registered URLs are fetched).
- **No WAF, bot protection or error-monitoring service.** Vercel's firewall and a Sentry-style tool are suggested; none is configured.
- **HSTS `includeSubDomains` / `preload`** are off (`SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`). Turn them on only when every subdomain of the domain is HTTPS-only forever; preloading is very hard to undo.
- **Postgres has not been tested here.** CI has an informational Postgres job; treat production database behaviour as unproven until it is green.
- **Admin URL** can be moved with `ADMIN_URL`; that reduces probing only.
- **No penetration test or third-party review** has been done.

## Reporting a vulnerability
Owner to fill in a contact address (for example a `security@` mailbox) and publish it at `/.well-known/security.txt` once a domain exists.

## Owner decisions still needed
1. Who the qualified veterinarian reviewers are (governance depends on it).
2. Whether to require 2FA for all staff roles (recommended: yes).
3. HSTS preload and subdomain policy.
4. Where errors and logs go (Sentry, Vercel logs drain, etc.).
