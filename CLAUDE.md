# Veterinary Intelligence Platform

Follow the master roadmap phases in [docs/ROADMAP.md](docs/ROADMAP.md). Before structural work read docs/ROADMAP.md, docs/ARCHITECTURE.md, docs/DATA_MODEL.md, and docs/CLINICAL_GOVERNANCE.md.

Layout: `web/` Next.js frontend (read [web/AGENTS.md](web/AGENTS.md): this Next.js version has breaking changes), `api/` Django backend, `infra/`, `docs/`.

Hard rules: never invent medical data, doses, prices or references; nothing scraped is published without review; calculations are deterministic code; no country-specific hardcoding; no secrets in git.
