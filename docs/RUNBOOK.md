# Runbook

Operational procedures. Commands run from `api/` with the production environment (for example `vercel env pull` into a local, ignored file) unless stated.

## First deployment
1. Create the Neon database; copy the **pooled** connection string with `sslmode=require` (never commit it).
2. Deploy the API project first (root `api`), then the web project (root `web`); see `DEPLOYMENT.md` for the variables.
3. From a machine with the production variables: `python manage.py migrate`, `createcachetable`, `seed_reference`, `createsuperuser`.
4. Do **not** run `seed_dev_catalog` in production (fictional data) and keep `SHOW_DEVELOPMENT_DATA=false`.
5. Sign in to the Django admin, create the reviewer accounts and set their roles. Only veterinarian-reviewer and admin roles can sign off clinical data.
6. Check `GET /api/v1/health/` (database reachable) and load the web home page.
7. Set `CRON_SECRET` if the scheduled link check and feeds should run; set `ANTHROPIC_API_KEY` only if the assistant should be on.

## Routine
| When | Task |
|---|---|
| Daily | Review the panel: review queue, price submissions, listings, question reports, automation (broken sources) |
| Weekly | Read `AssistantLog` in the Django admin (if the assistant is on); look at audit-log entries for unexpected actors |
| Before each release | `pip-audit -r api/requirements.txt`, `npm audit`, CI green, `manage.py check --deploy` with production settings |
| Monthly | Rotate nothing by default; rotate immediately after any suspected leak (below) |

## Deploy and roll back
- Deploys happen from `main` through Vercel. **Migrations are not run automatically**: apply them manually, backward-compatible first (add columns nullable, deploy code, then tighten).
- Roll back the web or API by promoting the previous deployment in Vercel. If a migration was applied that the old code cannot use, restore from backup instead (below).

## Backups and restore (Neon)
- Neon keeps point-in-time history for the retention window of your plan. Confirm the window in the Neon console and raise it if reviewers' work must be recoverable longer.
- To restore: in the Neon console create a branch from the desired timestamp, verify the data there, then either point `DATABASE_URL` at the branch or restore it over the main branch. Record the incident and the time range lost.
- Take a logical dump before risky migrations: `pg_dump "$DATABASE_URL" -Fc -f before-migration.dump`; store it outside the repo.
- The `AuditLog` and `simple_history` tables are part of the database, so a restore also rolls back review history; note that in the incident record.

## Secret rotation
| Secret | Effect of rotating | Steps |
|---|---|---|
| `SECRET_KEY` | Signs sessions and CSRF: **all users are logged out** | Set a new value on the API project, redeploy |
| Database password | Downtime until both sides agree | Reset the role password in Neon, update `DATABASE_URL`, redeploy |
| `CRON_SECRET` | Scheduled tasks fail until updated | Change it in the API project (Vercel Cron uses the same variable) |
| `ANTHROPIC_API_KEY` | Assistant stops until updated | Create a new key, update, revoke the old one |
If a Neon connection string was ever pasted into chat, email or a ticket, rotate it at once.

## Incidents
- **Wrong medical data was published:** in the review panel set the record to `deprecated` or `needs verification` (it disappears from public pages immediately; history and audit log are kept), tell the reviewer, fix the source, re-review.
- **Bad listing or price live:** reject it in the panel; three reports also pull a listing back automatically. Ban the account by clearing "active" in the Django admin.
- **Suspected account takeover of staff:** deactivate the account in the Django admin, rotate `SECRET_KEY` (logs everyone out), review the audit log for that actor, restore records if needed.
- **Assistant gave a bad answer:** open the `AssistantLog` entry (question, records used, answer). If the source record is wrong, fix it as above; if the checks let something through, add a failing test in `apps/assistant/tests` before changing code. Setting `ANTHROPIC_API_KEY` empty switches the assistant off instantly.
- **Automation misbehaving:** disable the feed in the Django admin (feeds are disabled by default) and unset `CRON_SECRET` to stop all scheduled calls.
- **Site down:** check Vercel status and deployment logs, then `GET /api/v1/health/`; a failing database check means Neon (status page, connection limit, suspended compute).

## Contacts to fill in
Owner, on-call reviewer, Neon and Vercel account owners.
