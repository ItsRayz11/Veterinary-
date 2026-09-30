"""Deterministic price analytics. Exact decimals; never mixes currencies, price types or packs."""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from .selectors import current_prices

TWO = Decimal("0.01")


def _pct(latest: Decimal, previous: Decimal) -> Decimal:
    return ((latest - previous) / previous * 100).quantize(TWO, rounding=ROUND_HALF_UP)


def price_series(records) -> list[dict]:
    """One series per (pack, country, region, city, price type, currency), oldest point first.

    `records` are published PriceRecords in any order. change_* compare the latest point with the
    one before it; they are None for a single observation.
    """
    groups: dict[tuple, list] = defaultdict(list)
    for r in records:
        key = (r.pack_id, r.country_id, r.region, r.city, r.price_type, r.currency)
        groups[key].append(r)
    out = []
    for rows in groups.values():
        rows.sort(key=lambda r: (r.observed_on, r.pk))
        first = rows[0]
        amounts = [r.amount for r in rows]
        latest = rows[-1]
        change = pct = None
        direction = "none"
        if len(rows) > 1:
            previous = rows[-2].amount
            change = latest.amount - previous
            pct = _pct(latest.amount, previous)
            direction = "up" if change > 0 else "down" if change < 0 else "same"
        out.append(
            {
                "pack_id": first.pack_id,
                "pack": (
                    f"{first.pack.dosage_form.name} {first.pack.pack_size_value.normalize():f}"
                    f" {first.pack.pack_size_unit.code}"
                ),
                "country": first.country.iso2,
                "region": first.region,
                "city": first.city,
                "price_type": first.price_type,
                "currency": first.currency,
                "points": [{"date": r.observed_on, "amount": str(r.amount)} for r in rows],
                "latest": str(latest.amount),
                "min": str(min(amounts)),
                "max": str(max(amounts)),
                "change": str(change) if change is not None else None,
                "change_percent": str(pct) if pct is not None else None,
                "direction": direction,
            }
        )
    out.sort(key=lambda s: (s["pack"], s["country"], s["region"], s["city"], s["price_type"]))
    return out


def region_comparison(records) -> list[dict]:
    """Latest price per region for the same pack, country, price type and currency.

    Only groups with at least two distinct regions are returned. `records` must be newest-first.
    """
    groups: dict[tuple, dict[str, object]] = defaultdict(dict)
    for r in current_prices(records):
        label = r.region or r.city
        if not label:
            continue
        groups[(r.pack_id, r.country_id, r.price_type, r.currency)].setdefault(label, r)
    out = []
    for by_region in groups.values():
        if len(by_region) < 2:
            continue
        rows = sorted(by_region.items(), key=lambda kv: (kv[1].amount, kv[0]))
        first = rows[0][1]
        low, high = rows[0][1].amount, rows[-1][1].amount
        out.append(
            {
                "pack_id": first.pack_id,
                "pack": (
                    f"{first.pack.dosage_form.name} {first.pack.pack_size_value.normalize():f}"
                    f" {first.pack.pack_size_unit.code}"
                ),
                "country": first.country.iso2,
                "price_type": first.price_type,
                "currency": first.currency,
                "regions": [
                    {"region": label, "amount": str(r.amount), "observed_on": r.observed_on}
                    for label, r in rows
                ],
                "spread": str(high - low),
                "spread_percent": str(_pct(high, low)),
            }
        )
    return out
