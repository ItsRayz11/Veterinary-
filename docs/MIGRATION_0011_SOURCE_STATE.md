# Migration `automation.0011_source_state_length`

## Problem
`RecordAssessment.source_state` was `varchar(16)`, but the assessment logic can produce
`linked_unverified` (17 characters). PostgreSQL raises `StringDataRightTruncation`; SQLite does not
enforce lengths, so only the Postgres CI job saw it (3 failing tests on `main`).

## Change
- `source_state`: `max_length` 16 to 32 (`AlterField`, no data change).
- `assessment.SOURCE_STATES` lists every value; `tests/test_field_lengths.py` checks them against
  the column (this check works on SQLite, so the gap cannot reopen unnoticed) and checks that the
  other assessment columns (`recommendation`, `primary_issue`, `image_state`) fit their longest values.
- Audit: the other bounded columns written by the assessment fit (`recommendation` longest 16 of 24,
  `primary_issue` longest 20 of 30, `image_state` 8 of 12, `trust_level`, `risk`).
  I did not audit every `CharField` in the project.

## Database behaviour
Widening a `varchar` on PostgreSQL is a catalogue-only change (no table rewrite) and takes a brief
`ACCESS EXCLUSIVE` lock. The existing indexes stay valid. Verified locally on a disposable PostgreSQL:
0010 to 0011 (16 to 32), reverse (back to 16), forward again.

## Deployment sequencing (not done; needs owner approval)
1. Deploy the migration before, or together with, any code that can write a 17-character state.
   The old code never wrote one successfully, so applying the migration first is safe.
2. Run `python manage.py migrate automation` against the production database. Not run by me.
3. Assess records again afterwards if assessments failed in the meantime (records whose source is
   linked but unverified could not be saved).

## Rollback
Rolling back `0011` is deliberately non-destructive: the reverse step does **not** narrow the column
(the migration's `WidenOnly` operation skips the database change when reversed). After
`migrate automation 0010` the Django state says 16 but the database column stays 32, which is harmless
and cannot fail or lose values. No assessment rows are deleted. Verified on local PostgreSQL:
0010 (16), 0011 (32), back to 0010 (column stays 32), forward again (32). Narrowing the column later,
if ever wanted, should be a separate reviewed migration after checking for longer values.

## Staged release checklist (nothing here has been run against production)
1. Review and approve this PR; confirm `api-postgres` is green (703 passed on GitHub, PostgreSQL 17).
2. **Warning:** `api/vercel.json` runs `migrate` on production builds, so merging to `main` migrates
   production automatically. Run the migration on staging first (`python manage.py migrate automation`
   against a staging database copy), check `\d automation_recordassessment` shows `character varying(32)`.
3. On staging, run the review pipeline once and confirm assessments with `linked_unverified` save.
4. Then, with explicit owner approval, merge; watch the production build log for `automation.0011`.
5. After deploy: re-run the review pipeline so records that could not be assessed are assessed;
   check the staff review queue loads and the three formerly failing flows work.

## Verification limits
Local PostgreSQL was a disposable bundled build without contrib extensions, so 8 trigram tests failed
locally. On GitHub (PostgreSQL 17 service image, `pg_trgm` available) the whole suite passes: 703 passed.
