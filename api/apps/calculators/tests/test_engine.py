import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from apps.calculators import engine

VECTORS = json.loads(
    (Path(__file__).resolve().parents[4] / "shared" / "calc-vectors.json").read_text("utf-8")
)["cases"]


@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_shared_vectors(case):
    fn = getattr(engine, case["fn"])
    if case.get("error"):
        with pytest.raises(engine.CalcError):
            fn(**case["input"])
        return
    result = fn(**case["input"])
    for key, expected in case["expected"].items():
        assert result.values[key] == Decimal(expected), key


def test_dose_calc_warns_above_maximum_but_does_not_clip():
    r = engine.dose_calc(500, 10, 100, max_dose_mg=3000)
    assert r.values["total_mg"] == 5000
    assert r.warnings and "exceeds" in r.warnings[0]


def test_dose_calc_exposes_formula_and_steps():
    r = engine.dose_calc(400, 5, 100)
    assert "weight" in r.formula and len(r.steps) == 2 and not r.warnings


def test_no_float_drift():
    # 0.1 + 0.2 style traps: decimal arithmetic must give exact results
    assert engine.mg_to_ml("0.3", "0.1").values["volume_ml"] == Decimal("3")


def test_withdrawal_end():
    r = engine.withdrawal_end(datetime(2026, 1, 1, 8, 0), 96)
    assert r.extra["eligible_from"] == datetime(2026, 1, 5, 8, 0)
    with pytest.raises(engine.CalcError):
        engine.withdrawal_end(datetime(2026, 1, 1), -1)


def test_round_display_half_up():
    assert engine.round_display(Decimal("2.675"), 2) == Decimal("2.68")
