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
| API (Django) | Vercel (second project, Root Directory `api`) | see "API on Vercel" below |
| Workers / Redis | same host | Phase 10 |

## Production checklist (partial)
- `DEBUG=false` (enables secure cookies, HTTPS redirect, HSTS), real `SECRET_KEY`
- `SHOW_DEVELOPMENT_DATA=false`
- Create a superuser and the reviewer accounts through the admin

## API on Vercel
Config is in `api/pyproject.toml` (`[tool.vercel] entrypoint`) and `api/vercel.json` (collectstatic at build, function excludes). Static/admin assets are served by WhiteNoise.
1. Create a Vercel project from the repo with **Root Directory = `api`** (Python 3.12).
2. Env vars: `DEBUG=false`, `SECRET_KEY`, `DATABASE_URL` (Neon pooled), `ALLOWED_HOSTS=<api-host>`, `CORS_ALLOWED_ORIGINS=https://<web-host>`, `CSRF_TRUSTED_ORIGINS=https://<web-host>`, `CACHE_URL=dbcache://django_cache`, `SHOW_DEVELOPMENT_DATA=false`.
3. One-off, from a machine with the same env: `python manage.py migrate`, `python manage.py createcachetable`, `python manage.py seed_reference`, `python manage.py createsuperuser`. Migrations are not run on deploy.
4. On the web project set `API_URL=https://<api-host>`.
- `requirements.txt` is runtime only; tests/lint use `requirements-dev.txt`.
- Throttling needs the shared DB cache (`CACHE_URL`); the default in-memory cache is per serverless instance and would not enforce limits.
- Serverless limits: no background workers (Phase 10 needs a separate host or Vercel Cron), 30 s function cap.
- Local test runs over Neon can collide with a leftover `test_<db>`; run tests with `DATABASE_URL=sqlite:///...` or a local Postgres.

## Web on Vercel
Project Root Directory = `web`. Env vars: `API_URL` (server-side proxy target and data fetching), `NEXT_PUBLIC_API_URL` (only for the Django-admin link in the review panel), `NEXT_PUBLIC_SITE_URL` (canonical origin for sitemap/robots). Deploy the API first so the proxy target exists. `npm run build` was verified locally against a running API.
