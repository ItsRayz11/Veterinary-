"""The review pipeline: one idempotent, time-boxed pass over records waiting for review.

For each record that is new, changed or stale:  link sources -> find images -> (probe links,
store eligible images) -> assess (group, completeness, duplicates, change detection,
recommendation). It never changes a record's review status: publication stays with a person
(`apps.core.review`) or with a fully approved regulator DataSource (`publishing.py`).

It runs as the `review-pipeline` task (Vercel cron, `manage.py run_task review-pipeline`, or the
admin "Run now" button). Re-running is harmless; a run that hits its time budget simply leaves the
rest for the next one (never-assessed records first).
"""

import time

from apps.core.review import QUEUE_STATUSES, publishable_models
from apps.sources import linking

from . import assessment, images, tasks

DEFAULT_LIMIT = 150
DEFAULT_BUDGET = 22.0  # seconds; Vercel stops functions at 30 s (api/vercel.json)
LINK_PROBE_LIMIT = 12


def has_source_evidence(record) -> bool:
    return bool(getattr(record, "source_url", "") or getattr(record, "wikidata_id", ""))


def prepare(record) -> dict:
    """Link sources and discover images for one record. Safe to call repeatedly."""
    out = {"created_sources": 0, "created_links": 0, "problems": []}
    if has_source_evidence(record):
        r = linking.link_record(record)
        out |= {
            "created_sources": r.created_sources,
            "created_links": r.created_links,
            "problems": r.problems,
        }
    images.discover(record)
    return out


def run_review_pipeline(
    limit: int = DEFAULT_LIMIT, budget_seconds: float = DEFAULT_BUDGET, clock=time.monotonic
) -> dict:
    started = clock()
    summary = {
        "sources_merged": 0,
        "records": 0,
        "sources_created": 0,
        "links_created": 0,
        "assessed": 0,
        "images": {},
        "links_probed": 0,
        "stopped_early": False,
    }
    summary["sources_merged"] = linking.dedupe_sources()["merged"]

    queue = [s.value for s in QUEUE_STATUSES]
    everything = assessment.all_statuses()
    batch = []
    for statuses in (queue, everything):  # people-waiting records first, then the rest
        for model in publishable_models().values():
            room = limit - len(batch)
            if room <= 0:
                break
            have = {(type(r), r.pk) for r in batch}
            batch += [
                r
                for r in assessment.stale_records(model, statuses, room)
                if (type(r), r.pk) not in have
            ][:room]

    prepared = []
    for record in batch:
        if clock() - started > budget_seconds * 0.5:
            summary["stopped_early"] = True
            break
        res = prepare(record)
        summary["sources_created"] += res["created_sources"]
        summary["links_created"] += res["created_links"]
        prepared.append(record)
    summary["records"] = len(prepared)

    remaining = budget_seconds - (clock() - started)
    if remaining > 4:  # reachability of newly linked sources, so eligibility can be decided
        probe = tasks.check_source_links(limit=LINK_PROBE_LIMIT, budget_seconds=remaining * 0.35)
        summary["links_probed"] = probe["checked"]
    remaining = budget_seconds - (clock() - started)
    if remaining > 3:
        summary["images"] = images.process_pending(limit=5, budget_seconds=remaining * 0.5)

    for record in prepared:
        if clock() - started > budget_seconds:
            summary["stopped_early"] = True
            break
        record.refresh_from_db()
        assessment.assess(record)
        summary["assessed"] += 1
    return summary
