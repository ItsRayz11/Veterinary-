"""Bulk actions on the review backlog, with a preview step and resumable chunked execution.

Safety model:
  * A bulk action is a loop over the single-record code paths. It has no privileges of its own:
    approval goes through `apps.core.review.set_review_status` (linked source, sign-off roles,
    no self-approval, no development data) and is additionally limited to records whose fresh
    assessment is `safe_batch` (low-risk kind, verified source and licence, complete, no duplicate).
  * `preview` changes nothing. `start` freezes the previewed record list into a BulkOperation;
    `step` works through it a few records at a time, so every request fits the platform time
    limit and progress survives a closed browser. Eligibility is re-checked per record at
    execution time, so a record that changed after the preview is skipped, not approved.
  * Every outcome is stored on the operation and written to the audit log.
"""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.core.models import AuditLog, ReviewStatus
from apps.core.review import publishable_models, set_review_status
from apps.sources import linking
from apps.sources.models import SourceLink

from . import assessment, images, r2
from .models import BulkOperation, BulkStatus, ImageAsset, ImageStatus

MAX_TARGETS = 2000
MAX_RESULTS = 1500
ACTIONS = {
    "link_sources": ("Repair source links", 40),
    "revalidate": ("Re-validate metadata", 40),
    "process_images": ("Process images", 4),
    "approve_safe": ("Approve safe records", 25),
}
APPROVAL_STATUS = ReviewStatus.VERIFIED


def get(model_key: str, pk: int):
    model = publishable_models().get(model_key)
    return model.objects.filter(pk=pk).first() if model else None


def _plan(action: str, record, user) -> tuple[bool, str]:
    """Would `action` do something useful for this record right now? (eligible, why/what)."""
    a = assessment.assess(record)
    if action == "link_sources":
        cands = linking.source_candidates(record)
        if not cands:
            return False, "no source URL on the record to link"
        if a.source_state in ("linked_ok",):
            return False, "already linked and verified"
        return True, f"link {len(cands)} source URL(s) to the registry and validate"
    if action == "revalidate":
        n = SourceLink.objects.filter(
            content_type=ContentType.objects.get_for_model(record), object_id=record.pk
        ).count()
        return (True, f"re-check {n} linked source(s)") if n else (False, "no linked source")
    if action == "process_images":
        if a.image_state not in ("pending", "failed"):
            return False, f"image state is '{a.image_state}'"
        if not r2.configured():
            return False, "Cloudflare R2 is not configured on the server"
        return True, "store eligible image(s) in R2"
    if action == "approve_safe":
        if not user.can_approve_clinical:
            return False, "your role cannot sign off records"
        if a.recommendation != "safe_batch":
            reason = assessment.RECOMMENDATIONS.get(a.recommendation, a.recommendation)
            first = next(iter(a.issues), "")
            return False, f"{reason}" + (
                f" ({assessment.ISSUES.get(first, first)})" if first else ""
            )
        if getattr(record, "submitted_by_id", None) == user.pk:
            return False, "cannot approve your own submission"
        return True, f"set status to '{APPROVAL_STATUS.label}' (source and licence verified)"
    raise ValueError("Unknown bulk action.")


def preview(action: str, targets: list[tuple[str, int]], user) -> dict:
    """What `action` would do to each target. Nothing is changed beyond refreshing assessments."""
    if action not in ACTIONS:
        raise ValueError("Unknown bulk action.")
    targets = targets[:MAX_TARGETS]
    rows, eligible, skipped = [], [], {}
    for model_key, pk in targets:
        rec = get(model_key, pk)
        if rec is None:
            skipped["record no longer exists"] = skipped.get("record no longer exists", 0) + 1
            continue
        ok, detail = _plan(action, rec, user)
        if ok:
            eligible.append((model_key, pk))
        else:
            skipped[detail] = skipped.get(detail, 0) + 1
        if len(rows) < 100:
            rows.append(
                {"model": model_key, "id": pk, "label": str(rec), "eligible": ok, "detail": detail}
            )
    return {
        "action": action,
        "label": ACTIONS[action][0],
        "selected": len(targets),
        "eligible": len(eligible),
        "skipped": sum(skipped.values()),
        "skipped_reasons": dict(sorted(skipped.items(), key=lambda kv: -kv[1])),
        "sample": rows,
        "targets": eligible,
    }


def start(action: str, targets: list[tuple[str, int]], user, reason: str = "") -> BulkOperation:
    """Freeze the (already previewed) eligible targets into a new operation."""
    op = BulkOperation.objects.create(
        actor=user,
        action=action,
        reason=reason[:300],
        targets=[list(t) for t in targets[:MAX_TARGETS]],
    )
    AuditLog.objects.create(
        actor=user,
        action="bulk_operation_started",
        object_type=BulkOperation._meta.label,
        object_id=str(op.pk),
        after={"action": action, "targets": op.total},
        reason=reason[:300],
    )
    if not op.targets:
        _finish(op)
    return op


def _run_one(op: BulkOperation, record) -> tuple[str, str]:
    """Execute the action for one record. Returns (outcome, detail)."""
    ok, why = _plan(op.action, record, op.actor)  # re-check at execution time
    if not ok:
        return "skipped", why
    if op.action == "link_sources":
        r = linking.link_record(record)
        assessment.assess(record)
        return "ok", f"{r.created_sources} source(s) created, {r.created_links} link(s) added"
    if op.action == "revalidate":
        links = SourceLink.objects.filter(
            content_type=ContentType.objects.get_for_model(record), object_id=record.pk
        ).select_related("source")
        results = [linking.validate_source(lk.source)[0].value for lk in links]
        assessment.assess(record)
        return "ok", ", ".join(results)
    if op.action == "process_images":
        images.discover(record)
        ct = ContentType.objects.get_for_model(record)
        states = []
        for asset in ImageAsset.objects.filter(
            content_type=ct,
            object_id=record.pk,
            status__in=(ImageStatus.PENDING, ImageStatus.FAILED),
        ):
            states.append(images.retry(asset).status)
        assessment.assess(record)
        bad = [s for s in states if s != ImageStatus.STORED]
        return ("failed", "image not stored: " + ", ".join(bad)) if bad else ("ok", "stored")
    if op.action == "approve_safe":
        set_review_status(
            record,
            APPROVAL_STATUS,
            op.actor,
            reason=f"Bulk safe approval #{op.pk}: {op.reason}"[:300],
        )
        assessment.assess(record)
        return "ok", f"status set to {APPROVAL_STATUS.value}"
    raise ValueError("Unknown bulk action.")


def _finish(op: BulkOperation) -> None:
    op.status = BulkStatus.PARTIAL if op.failed else BulkStatus.DONE
    op.finished_at = timezone.now()
    op.save()
    AuditLog.objects.create(
        actor=op.actor,
        action="bulk_operation_finished",
        object_type=BulkOperation._meta.label,
        object_id=str(op.pk),
        after={"succeeded": op.succeeded, "skipped": op.skipped, "failed": op.failed},
        reason=op.action,
    )


def step(op: BulkOperation, chunk: int | None = None) -> BulkOperation:
    """Process the next few targets. Safe to call repeatedly; a finished operation is unchanged."""
    if op.status != BulkStatus.RUNNING:
        return op
    size = chunk or ACTIONS[op.action][1]
    batch = op.targets[op.cursor : op.cursor + size]
    audit = []
    for model_key, pk in batch:
        rec = get(model_key, pk)
        if rec is None:
            outcome, detail = "skipped", "record no longer exists"
        else:
            try:
                outcome, detail = _run_one(op, rec)
            except (PermissionDenied, ValidationError) as exc:
                outcome, detail = "failed", " ".join(getattr(exc, "messages", [str(exc)]))[:200]
            except Exception as exc:  # noqa: BLE001 - one bad record must not stop the batch
                outcome, detail = "failed", f"Unexpected {type(exc).__name__}"
        if outcome == "ok":
            op.succeeded += 1
        elif outcome == "skipped":
            op.skipped += 1
        else:
            op.failed += 1
        if len(op.results) < MAX_RESULTS:
            label = str(rec) if rec else ""
            op.results.append(
                {"model": model_key, "id": pk, "label": label, "outcome": outcome, "detail": detail}
            )
        if op.action != "approve_safe":  # approvals are audited by set_review_status itself
            audit.append(
                AuditLog(
                    actor=op.actor,
                    action=f"bulk_{op.action}",
                    object_type=publishable_models()[model_key]._meta.label,
                    object_id=str(pk),
                    after={"operation": op.pk, "outcome": outcome, "detail": detail},
                    reason=op.reason,
                )
            )
    op.cursor += len(batch)
    AuditLog.objects.bulk_create(audit)
    if op.cursor >= op.total:
        _finish(op)
    else:
        op.save()
    return op


def retry_failed(op: BulkOperation, user) -> BulkOperation:
    failed = [[r["model"], r["id"]] for r in op.results if r["outcome"] == "failed"]
    new = start(op.action, [tuple(t) for t in failed], user, reason=f"Retry of #{op.pk}")
    new.retry_of = op
    new.save(update_fields=["retry_of", "updated_at"])
    return new


def serialize(op: BulkOperation, *, with_results: bool = False) -> dict:
    out = {
        "id": op.pk,
        "action": op.action,
        "label": ACTIONS.get(op.action, (op.action,))[0],
        "status": op.status,
        "total": op.total,
        "processed": op.cursor,
        "succeeded": op.succeeded,
        "skipped": op.skipped,
        "failed": op.failed,
        "reason": op.reason,
        "retry_of": op.retry_of_id,
        "actor": getattr(op.actor, "username", None),
        "created_at": op.created_at,
        "finished_at": op.finished_at,
    }
    if with_results:
        out["results"] = op.results
    return out
