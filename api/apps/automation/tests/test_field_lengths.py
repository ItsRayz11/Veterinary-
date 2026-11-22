"""PostgreSQL enforces varchar length, SQLite does not: guard values written by code against columns."""

import re
from pathlib import Path

from apps.automation import assessment
from apps.automation.models import RecordAssessment


def test_every_source_state_fits_its_column():
    limit = RecordAssessment._meta.get_field("source_state").max_length
    assert max(map(len, assessment.SOURCE_STATES)) <= limit


def test_source_states_list_matches_what_the_code_can_produce():
    src = Path(assessment.__file__).read_text(encoding="utf-8")
    assigned = set(re.findall(r'\bstate = "([a-z_]+)"', src))
    assigned |= set(re.findall(r'state = "([a-z_]+)" if', src))
    assert assigned <= set(assessment.SOURCE_STATES)
    assert "linked_unverified" in assessment.SOURCE_STATES


def test_other_assessment_columns_fit_their_longest_values():
    fields = {
        f.name: f.max_length
        for f in RecordAssessment._meta.get_fields()
        if hasattr(f, "max_length")
    }
    assert fields["recommendation"] >= len("regulator_review")  # longest recommendation
    assert fields["primary_issue"] >= max(map(len, assessment.ISSUES))
    assert fields["image_state"] >= len("rejected")


def test_migration_0011_does_not_narrow_the_column_on_rollback():
    import importlib

    mig = importlib.import_module("apps.automation.migrations.0011_source_state_length")
    (op,) = mig.Migration.operations
    called = []

    class Editor:
        def alter_field(self, *a, **k):
            called.append(1)

    op.database_backwards("automation", Editor(), None, None)
    assert called == []
