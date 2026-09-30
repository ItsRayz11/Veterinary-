# Testing

## API (`api/`)
- Install: `pip install -r requirements-dev.txt`
- Run on SQLite (fast, safe): `DATABASE_URL=sqlite:///test-local.sqlite3 python -m pytest -q`
- Do not run the suite against the Neon URL from `.env`: it creates `test_<db>` on the remote server, is slow, and a crashed run leaves that database behind (the next run then fails with "already exists").
- Lint/format: `ruff check . && ruff format --check .`; migrations: `python manage.py makemigrations --check --dry-run`
- Fixtures: `seed_dev_catalog` creates clearly-labelled development data (never verifiable). Tests must not depend on data the seed does not create; build what you need in the test.

## Web (`web/`)
- `npm run lint && npm run format && npm run typecheck && npm test && npm run build`
- `npm test` covers the calculator engine against `shared/calc-vectors.json` (same vectors as the Python engine) and the calculator registry with hand-computed values.
- Pages that call the API need it running (`API_URL`); `next build` does not, because API-backed index pages render on request.

## Real-browser check (manual)
`web/scripts/browser-check.mjs` drives Chrome against a production build: types into calculators, checks the service worker precaches, then stops the server to prove offline use and that private pages are never cached (13 checks; last run all passing). It needs `puppeteer-core` and is Windows-specific because it stops the server with PowerShell.

## Accessibility and mobile (manual)
`web/scripts/a11y-check.mjs` runs axe-core (WCAG 2.0-2.2 A/AA plus best practice) on 16 pages at 375 px and 1280 px in light and dark themes, and fails on horizontal overflow. `web/scripts/mfa-check.mjs` registers a user, turns on two-factor through the UI and checks sign-in with a wrong code and with a single-use recovery code. Both need `npm i --no-save puppeteer-core axe-core`, a production build on port 3100 and the API on port 8000 (set `CSRF_TRUSTED_ORIGINS=http://localhost:3100` for the API). Automated checks find only part of the problems; real screen-reader and device testing is still to be done by a person.

## Security sweep
`apps/core/tests/test_pentest_matrix.py` calls every API route with every method and hostile payloads as anonymous, plain and staff users (no 5xx; staff areas closed). Also run `bandit -r apps config -x "*/tests/*,*/migrations/*"`, `pip-audit -r requirements.txt` and `npm audit --omit=dev`.

## Postgres locally
Migrations over a remote Postgres take ~25 minutes to build a test database. Run the suite against a real database with `pytest --reuse-db` (creates `test_<name>` once, then reuses it) using the direct, non-pooled endpoint; the pooler leaves idle sessions that block dropping the test database.

## CI
`api` (SQLite, gating), `api-postgres` (informational until seen green) and `web`. Tests need `DEBUG=true` and a `SECRET_KEY` because `api/.env` is not in git; CI sets them (verified locally with `.env` hidden). Production-like check: `DEBUG=false SECRET_KEY=... python manage.py check --deploy` must be clean.

## Not covered yet
- Browser/mobile QA and accessibility audits (manual, Phase 14).
- End-to-end exam flow with real questions (none exist; API flow is covered by `apps/education/tests`).
