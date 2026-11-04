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

## Roles and permissions (Django groups, synced from `User.role`)
Setting a user's role in Admin > Users puts them in the matching "Role: …" group and turns on `is_staff` for staff roles (reviewer, veterinarian reviewer, editor, moderator, admin). Definitions: `api/apps/accounts/roles.py`. Reviewers and editors can edit and approve catalogue records but cannot delete them; only veterinarian reviewers and admins can sign off clinical data (`CLINICAL_GOVERNANCE.md`); only admins manage users and data sources. Every staff account must enrol two-factor. Tested end to end in `apps/pharma/tests/test_admin_workflow.py` (find an imported registration, open it with its target species and source, approve it, see "not reviewed" disappear on the public API).

## Review workflow
1. Admin > Product registrations: search by registration number or brand; filter by country, status, review state.
2. Open the record: target species (as stated by the regulator), history, and source links are on the page.
3. Edit if needed, then use the action "Set review status: Official regulatory source" (or the clinical statuses for doses).
4. The public API and species page update within about a minute (edge cache).
Unclassified drugs (no class yet): Admin > Generics > filter "Drug class: empty".
