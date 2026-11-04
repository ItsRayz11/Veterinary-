# Administration

## Where
- **Django admin** (all models, review actions, history, audit log): `https://veterinaryapi.vercel.app/<ADMIN_URL>` (default `/admin/`; set `ADMIN_URL` on the API project to move it). Login is required; staff must enrol two-factor (`REQUIRE_STAFF_MFA`, on in production). Nothing in it is reachable without a staff account.
- **Review panel** (queue, imports, automation, sources): `https://veterinary-alpha.vercel.app/admin-panel` for signed-in staff.
- Roles: reviewer / editor / admin groups; reviewers cannot approve their own edits (see `CLINICAL_GOVERNANCE.md`).

## Create the first administrator (secure procedure)
Run from a trusted machine, never paste the production `DATABASE_URL` into chat or git:
1. `cd api`, set `DATABASE_URL` (Neon pooled string) and `SECRET_KEY` in your shell only (for example from the Vercel dashboard > veterinaryapi > Settings > Environment Variables).
2. `python manage.py createsuperuser` and pick a long unique password.
3. Sign in at the admin URL; set up two-factor when prompted and store the recovery codes offline.
4. Create reviewer accounts in Admin > Users and put them in the reviewer group.

## Data pipeline
- Every production deploy runs `migrate`, `createcachetable` and `bootstrap_public_data` (reference data, drug-class tree, university import). It is idempotent and a failing university fetch never blocks a deploy.
- Imports are always created as "Imported, not reviewed". Approve or reject in Admin (University, Generic, Product have review actions) or the review panel.
- Source freshness and import errors: Admin > Automation > Data sources / runs.

## Backups and rollback
Before any manual production data change, create a Neon snapshot (Console > Branches > Snapshots) and note its name. Restore from the snapshot if needed. Code rollback: redeploy the previous Vercel deployment.
