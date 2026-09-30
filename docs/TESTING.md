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

## Not covered yet
- Browser/mobile QA and accessibility audits (manual, Phase 14).
- End-to-end exam flow with real questions (none exist; API flow is covered by `apps/education/tests`).
