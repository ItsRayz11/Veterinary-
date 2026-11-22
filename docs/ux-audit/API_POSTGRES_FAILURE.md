# `api-postgres` CI failure: root cause (not caused by this PR)

Failing on `main` (run 44749387894) and on this branch identically: 3 failed, 697 passed.
Tests: `test_bulk_approval_only_touches_safe_records_and_needs_a_signer`,
`test_status_change_writes_audit_and_shows_in_history`, `test_record_detail_shows_fields_and_sources`.
Error: `psycopg.errors.StringDataRightTruncation: value too long for type character varying(16)`.

## Cause
`api/apps/automation/models.py:362` declares `source_state = CharField(max_length=16)`, but
`api/apps/automation/assessment.py:196` produces the state `"linked_unverified"` (17 characters).
SQLite (the default test/dev database) does not enforce `varchar` length, so the `api` job passes;
PostgreSQL rejects the write. Introduced with commit efe1a2f (review pipeline), not by this PR.

## Why it matters
This is probably not only a test problem: on the production Postgres database, assessing a record
whose source is linked but unverified would raise a 500 (`DataError`) instead of saving. I have not
checked production data or logs and made no change there.

## Not fixed here
The fix is a model change plus a migration (e.g. `max_length=24`, `AlterField`). Schema and
migration changes are outside what this work was authorised to do, so nothing was changed. Needs a
decision from the API owner; the three failing tests are the regression test once it is fixed.
Check at the same time whether other state/choice columns have a value longer than their `max_length`.
