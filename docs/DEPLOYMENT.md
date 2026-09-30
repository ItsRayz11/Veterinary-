# Deployment and environments

## Database (Neon Postgres)
- Set `DATABASE_URL` in `api/.env` (git-ignored) or the host's secret store. Use the **pooled** connection string with `sslmode=require`.
- Never commit connection strings. If one is pasted into chat, email or an issue, rotate the password in the Neon console.
- Schema is applied with `python manage.py migrate`; reference data with `python manage.py seed_reference`.
- Tests on Postgres create a temporary `test_<db>` database; over a remote connection the suite is slow, so CI should use a local Postgres service container instead.
- Development-only records (`seed_dev_catalog`) must not be loaded on a production database.

## Services
| Service | Where | Notes |
|---|---|---|
| Web (Next.js) | Vercel | env `API_URL` = public API origin |
| API (Django) | always-on host (to decide) | env `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DEBUG=false` |
| Workers / Redis | same host | Phase 10 |

## Production checklist (partial)
- `DEBUG=false` (enables secure cookies, HTTPS redirect, HSTS), real `SECRET_KEY`
- `SHOW_DEVELOPMENT_DATA=false`
- Create a superuser and the reviewer accounts through the admin
