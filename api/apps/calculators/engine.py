"""Deterministic clinical arithmetic. Pure functions, no Django, no I/O, no clinical constants.

Every function takes explicit inputs (rates/concentrations come from the caller, ideally from a
verified DoseRegimen or the product label), validates them, and returns a CalcResult that exposes
the formula, the steps and any warnings. Mirrored in web/src/lib/calc/engine.ts; both are tested
against the same vectors in shared/calc-vectors.json.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

D = Decimal

WEIGHT_KG_RANGE = (D("0.001"), D("2000"))  # input sanity bounds, not clinical limits
LB_PER_KG = D("2.20462262185")


class CalcError(ValueError):
    """Impossible or missing input. Message is safe to show to the user."""


@dataclass
class CalcResult:
    formula: str
    values: dict[str, Decimal]
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)  # non-decimal outputs (e.g. datetimes)


def dec(value, name: str) -> Decimal:
    try:
        d = D(str(value))
    except Exception as exc:
        raise CalcError(f"{name} must be a number.") from exc
    if not d.is_finite():
        raise CalcError(f"{name} must be a finite number.")
    return d


def positive(value, name: str) -> Decimal:
    d = dec(value, name)
    if d <= 0:
        raise CalcError(f"{name} must be greater than zero.")
    return d


def round_display(value: Decimal, places: int = 2) -> Decimal:
    return value.quantize(D(1).scaleb(-places), rounding=ROUND_HALF_UP)


def to_kg(weight, unit: str = "kg") -> Decimal:
    w = positive(weight, "Weight")
    if unit == "kg":
        kg = w
    elif unit == "lb":
        kg = w / LB_PER_KG
    elif unit == "g":
        kg = w / 1000
    else:
        raise CalcError(f"Unsupported weight unit: {unit}")
    lo, hi = WEIGHT_KG_RANGE
    if not lo <= kg <= hi:
        raise CalcError(f"Weight must be between {lo} and {hi} kg.")
    return kg


def percent_to_mg_per_ml(percent) -> CalcResult:
    p = positive(percent, "Percent")
    if p > 100:
        raise CalcError("Percent (w/v) cannot exceed 100.")
    v = p * 10
    return CalcResult("mg/mL = % (w/v) x 10", {"mg_per_ml": v}, [f"{p}% x 10 = {v} mg/mL"])


def mg_to_ml(dose_mg, concentration_mg_per_ml) -> CalcResult:
    mg, c = positive(dose_mg, "Dose"), positive(concentration_mg_per_ml, "Concentration")
    v = mg / c
    return CalcResult("mL = mg / (mg/mL)", {"volume_ml": v}, [f"{mg} mg / {c} mg/mL = {v} mL"])


def ml_to_mg(volume_ml, concentration_mg_per_ml) -> CalcResult:
    ml, c = positive(volume_ml, "Volume"), positive(concentration_mg_per_ml, "Concentration")
    mg = ml * c
    return CalcResult("mg = mL x (mg/mL)", {"dose_mg": mg}, [f"{ml} mL x {c} mg/mL = {mg} mg"])


def dose_calc(
    weight, dose_mg_per_kg, concentration_mg_per_ml, weight_unit="kg", max_dose_mg=None
) -> CalcResult:
    """Total mg and mL for a mg/kg dose. Warns (never silently clips) above the sourced maximum."""
    kg = to_kg(weight, weight_unit)
    rate = positive(dose_mg_per_kg, "Dose rate")
    conc = positive(concentration_mg_per_ml, "Concentration")
    total_mg = kg * rate
    volume = total_mg / conc
    steps = []
    if weight_unit != "kg":
        steps.append(f"Weight: {weight} {weight_unit} = {kg} kg")
    steps += [
        f"Total dose: {kg} kg x {rate} mg/kg = {total_mg} mg",
        f"Volume: {total_mg} mg / {conc} mg/mL = {volume} mL",
    ]
    warnings = []
    if max_dose_mg is not None:
        cap = positive(max_dose_mg, "Maximum dose")
        if total_mg > cap:
            warnings.append(
                f"Calculated dose {round_display(total_mg)} mg exceeds the referenced maximum "
                f"of {cap} mg. Verify before administering."
            )
    return CalcResult(
        "total mg = weight (kg) x dose (mg/kg); volume mL = total mg / concentration (mg/mL)",
        {"weight_kg": kg, "total_mg": total_mg, "volume_ml": volume},
        steps,
        warnings,
    )


def dilution(stock_conc, target_conc, final_volume_ml) -> CalcResult:
    """C1 x V1 = C2 x V2. Concentrations in the same unit."""
    c1, c2 = positive(stock_conc, "Stock concentration"), positive(target_conc, "Target")
    v2 = positive(final_volume_ml, "Final volume")
    if c2 > c1:
        raise CalcError("Target concentration cannot be higher than the stock concentration.")
    v1 = c2 * v2 / c1
    return CalcResult(
        "V1 = (C2 x V2) / C1; diluent = V2 - V1",
        {"stock_volume_ml": v1, "diluent_ml": v2 - v1},
        [f"V1 = ({c2} x {v2}) / {c1} = {v1} mL", f"Diluent = {v2} - {v1} = {v2 - v1} mL"],
    )


def dehydration_deficit(weight, dehydration_percent, weight_unit="kg") -> CalcResult:
    kg = to_kg(weight, weight_unit)
    pct = positive(dehydration_percent, "Dehydration")
    if pct > 30:
        raise CalcError("Dehydration above 30% is outside the calculator's input range.")
    deficit = kg * pct * 10
    return CalcResult(
        "deficit (mL) = weight (kg) x dehydration (%) x 10",
        {"deficit_ml": deficit},
        [f"{kg} kg x {pct}% x 10 = {deficit} mL"],
    )


def daily_fluid_need(weight, ml_per_kg_per_day, weight_unit="kg") -> CalcResult:
    """Maintenance/replacement volume for a caller-supplied mL/kg/day rate (rate not built in)."""
    kg = to_kg(weight, weight_unit)
    rate = positive(ml_per_kg_per_day, "Fluid rate")
    ml = kg * rate
    return CalcResult(
        "mL/day = weight (kg) x rate (mL/kg/day)",
        {"ml_per_day": ml, "ml_per_hour": ml / 24},
        [f"{kg} kg x {rate} mL/kg/day = {ml} mL/day", f"{ml} / 24 = {ml / 24} mL/h"],
    )


def infusion_rate(volume_ml, hours) -> CalcResult:
    v, h = positive(volume_ml, "Volume"), positive(hours, "Duration")
    return CalcResult(
        "mL/h = volume / hours", {"ml_per_hour": v / h}, [f"{v} / {h} = {v / h} mL/h"]
    )


def drip_rate(volume_ml, hours, drops_per_ml) -> CalcResult:
    v, h, df = (
        positive(volume_ml, "Volume"),
        positive(hours, "Duration"),
        positive(drops_per_ml, "Drop factor"),
    )
    per_min = v * df / (h * 60)
    return CalcResult(
        "drops/min = volume (mL) x drop factor (gtt/mL) / (hours x 60)",
        {"drops_per_min": per_min, "seconds_per_drop": 60 / per_min},
        [f"{v} x {df} / ({h} x 60) = {per_min} drops/min"],
    )


def cri_rate(weight, dose_mcg_per_kg_min, concentration_mg_per_ml, weight_unit="kg") -> CalcResult:
    """Constant-rate infusion pump rate (mL/h) for a mcg/kg/min dose."""
    kg = to_kg(weight, weight_unit)
    dose = positive(dose_mcg_per_kg_min, "CRI dose")
    conc = positive(concentration_mg_per_ml, "Concentration")
    mcg_per_hour = dose * kg * 60
    ml_per_hour = mcg_per_hour / (conc * 1000)
    return CalcResult(
        "mL/h = dose (mcg/kg/min) x weight (kg) x 60 / (concentration (mg/mL) x 1000)",
        {"ml_per_hour": ml_per_hour, "mcg_per_hour": mcg_per_hour},
        [
            f"{dose} mcg/kg/min x {kg} kg x 60 = {mcg_per_hour} mcg/h",
            f"{mcg_per_hour} / ({conc} x 1000) = {ml_per_hour} mL/h",
        ],
    )


def drinking_water_dose(
    birds, avg_weight_kg, dose_mg_per_kg, water_litres_per_day, product_mg_per_g
) -> CalcResult:
    """Flock medication via drinking water: mg/L to achieve a mg/kg body-weight dose."""
    n = positive(birds, "Number of birds")
    bw = to_kg(avg_weight_kg, "kg")
    rate = positive(dose_mg_per_kg, "Dose rate")
    water = positive(water_litres_per_day, "Daily water intake (whole flock)")
    potency = positive(product_mg_per_g, "Product strength (mg active per g)")
    total_mg = n * bw * rate
    conc = total_mg / water
    product_g = total_mg / potency
    return CalcResult(
        "total mg = birds x avg weight (kg) x dose (mg/kg); mg/L = total mg / water (L/day); "
        "product g = total mg / strength (mg/g)",
        {"total_mg_per_day": total_mg, "mg_per_litre": conc, "product_g_per_day": product_g},
        [
            f"{n} x {bw} kg x {rate} mg/kg = {total_mg} mg/day",
            f"{total_mg} mg / {water} L = {conc} mg/L",
            f"{total_mg} mg / {potency} mg/g = {product_g} g product/day",
        ],
        ["Assumes all birds drink the stated water volume; check actual intake."],
    )


def withdrawal_end(last_treatment: datetime, withdrawal_hours) -> CalcResult:
    """Earliest date/time products may enter the food chain. Hours come from a sourced record."""
    h = dec(withdrawal_hours, "Withdrawal period")
    if h < 0:
        raise CalcError("Withdrawal period cannot be negative.")
    end = last_treatment + timedelta(hours=float(h))
    return CalcResult(
        "end = last treatment + withdrawal period",
        {"withdrawal_hours": h},
        [f"{last_treatment.isoformat()} + {h} h = {end.isoformat()}"],
        extra={"eligible_from": end},
    )
