# Automation plan: what still needs a person, and what does not have to

Status 2026-11-27. Builds on `REVIEW_PIPELINE.md`, `DATA_SYNC.md` and `PUBLICATION_TIERS.md`.

## The line that does not move

Per `CLAUDE.md` and `CLINICAL_GOVERNANCE.md`: doses, withdrawal periods, interactions,
contraindications and any other clinical statement are never published without a qualified
reviewer. "Totally automatic" therefore means: **machines do all collection, checking, sorting,
retrying, expiring and reminding; people only make the clinical and legal decisions**, and those
decisions arrive pre-checked, grouped and one click away.

## Already automatic (verified in code)

| Job | Where | Schedule |
| --- | --- | --- |
| Source link health | `tasks.check_source_links` | Vercel cron 03:00 |
| News/feed intake, spam screening (`looks_suspicious`) | `tasks.run_all_feeds` | 04:00 |
| Data-source reachability | `tasks.check_data_sources` | 05:00 |
| University import (one country per run) | `tasks.universities_sync` | 05:30 |
| Review pipeline: link sources, images to R2, assess, group, flag duplicates | `pipeline.run_review_pipeline` | 06:00 |
| Regulator imports with hold-on-anomaly guard | `sync_data_sources` (GitHub Actions) | 06:00 |
| Factual tier auto-publishing per approved source | `publishing.publish_after_sync` | after each sync |
| Listing expiry (jobs, scholarships) | `ListingQuerySet` filters on `expires_on` | on read |
| Interrupted runs closed as failed | `tasks.run_task` | each run |

## Gaps, in priority order

### 1. Tell staff when something needs them (highest value, small)
Today nothing reaches staff unless they open `/admin-panel`. Push (`apps/push/service.notify`) is
only used for listing owners.
- Add a `staff-digest` task: failed `JobRun`s, sources with `consecutive_failures >= 3`, held syncs
  (`held_reason`), new `ClientError` fingerprints, review-queue size by kind.
- Send it as a web push to staff with a role that can act on it, and optionally an email.
- Skip sending when there is nothing to report.

### 2. Detect jobs that did not run at all (small)
A cron that stops firing (secret rotated, project paused) leaves no `JobRun` and no error.
- In the digest, compare each task's last `JobRun.created_at` with its schedule; flag anything
  older than 26 h as "missed".
- Show the same flag in the automation tab.

### 3. Wire up the price outlier check (small, a real disconnection)
`policy.is_price_outlier` is implemented and unit-tested, but no production code calls it.
- On `PriceSubmission` create: compare it with recent approved prices for the same product and
  currency. Outliers go to the queue marked "outlier"; plausible ones are grouped for one-click
  batch approval.
- Never auto-approve. Prices are user claims; the hard rules forbid inventing prices, and
  unreviewed claims are effectively that.

### 4. Retry failed images on their own (small)
`images.retry` exists but only the admin button calls it.
- In `review-pipeline`, retry `FAILED` assets with exponential backoff (1 d, 3 d, 7 d) up to
  `attempts < 4`; after that leave them for a person.

### 5. Close stale errors (small)
`ClientError.resolved` is only set by hand.
- Mark resolved when `last_seen` is older than 14 days. A new occurrence already reopens it
  (`service.py` sets `resolved=False`).

### 6. Turn failed searches into suggestions (medium)
`SearchMiss` is counted and resolved by hand.
- Weekly, match each frequent miss against reviewed brands, synonyms and ingredients (edit
  distance, transliteration). Propose "add synonym X → generic Y" as a review item.
- A person accepts it with one click.

### 7. Finish university coverage faster (small)
One country per run means a full refresh takes weeks.
- Process countries until the 30 s budget is nearly used. The pipeline is already time-boxed, so
  the same pattern applies.

### 8. Pre-fill the reviewer's decision (medium)
`RecordAssessment` already computes completeness, duplicates and a recommendation.
- Show it as the default choice in the review workspace, with reasons.
- Add keyboard shortcuts so a reviewer can approve, reject or request correction and move on.
- Sort the queue by "safe batch first".

### 9. Decisions only you can make (cannot be automated)
- Confirm licence terms for Health Canada DPD and US DailyMed, then enable their imports. The
  importers already exist.
- EMA UPD needs registered API credentials.
- Configure R2 (`R2_*` variables); until then every image stays `pending`.
- Set `DATA_SYNC_ENABLED=true` and the repo secrets so the GitHub Actions import runs.

## Suggested order
1, 2, 3, 5 together (about a day: one new task, one schedule, small model hooks, tests), then 4
and 7, then 6 and 8.
