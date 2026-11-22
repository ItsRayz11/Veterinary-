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
The reverse migration narrows the column to 16 and **fails if any row now holds a value longer than
16 characters** (it would, after any `linked_unverified` assessment is stored). To roll back, first
rewrite or delete those assessment rows (they are derived data and are recomputed), or leave the wider
column in place; it is harmless.

## Verification limits
Local PostgreSQL was a disposable bundled build without contrib extensions, so the `pg_trgm` DDL in
`pharma.0002` was skipped by a local test helper (not committed). Trigram search behaviour is therefore
not covered by the local Postgres run; GitHub's Postgres 17 job is the check for it.
