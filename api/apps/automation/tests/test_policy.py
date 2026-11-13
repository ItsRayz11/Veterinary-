from apps.automation.policy import Candidate, Decision, decide, is_price_outlier


def ok(**kw):
    base = dict(kind="job", source_verified=True, destination_ok=True)
    return Candidate(**{**base, **kw})


def test_verified_low_risk_publishes():
    assert decide(ok())[0] == Decision.PUBLISH


def test_clinical_never_publishes_even_when_everything_else_passes():
    for kind in ("dose", "treatment", "regulatory", "drug_reference", "mystery"):
        assert decide(ok(kind=kind, ai_confidence=0.99))[0] == Decision.REVIEW


def test_ai_assisted_and_unverified_go_to_review():
    assert decide(ok(ai_assisted=True))[0] == Decision.REVIEW
    assert decide(ok(source_verified=False))[0] == Decision.REVIEW
    assert decide(ok(destination_ok=False))[0] == Decision.REVIEW
    assert decide(ok(suspicious=True))[0] == Decision.REVIEW


def test_expired_and_duplicates_are_skipped():
    assert decide(ok(expired=True))[0] == Decision.SKIP
    assert decide(ok(is_duplicate=True))[0] == Decision.SKIP


def test_price_outlier():
    assert is_price_outlier(500, [10, 11, 12])
    assert not is_price_outlier(11, [10, 11, 12])
    assert not is_price_outlier(500, [10])
