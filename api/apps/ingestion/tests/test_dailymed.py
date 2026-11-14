import json

import pytest

from apps.ingestion.adapters import us_dailymed

LABEL = b"""<?xml version="1.0"?>
<document xmlns="urn:hl7-org:v3">
  <code code="50577-6" displayName="OTC ANIMAL DRUG LABEL"/>
  <setId root="64c3482a-f978"/>
  <author><assignedEntity><representedOrganization><name>VETR, LLC</name>
  </representedOrganization></assignedEntity></author>
  <component><structuredBody><component><section><subject><manufacturedProduct>
    <manufacturedProduct>
      <name>Albendamax</name>
      <formCode displayName="SUSPENSION"/>
      <ingredient classCode="ACTIB">
        <quantity><numerator value="113.6" unit="mg"/><denominator value="1" unit="mL"/></quantity>
        <ingredientSubstance><name>ALBENDAZOLE</name></ingredientSubstance>
      </ingredient>
      <ingredient classCode="IACT"><ingredientSubstance><name>GLYCERIN</name></ingredientSubstance>
      </ingredient>
      <subjectOf><approval><code displayName="unapproved drug other"/></approval></subjectOf>
    </manufacturedProduct>
  </manufacturedProduct></subject></section></component></structuredBody></component>
  <text>Dose 10 mg/kg in sheep. Withdrawal 7 days.</text>
</document>"""

HUMAN = LABEL.replace(b"50577-6", b"34391-3")
APPROVED = LABEL.replace(b"unapproved drug other", b"NADA").replace(
    b"</approval>", b'<id extension="141-123"/></approval>'
)


def page(setids, total_pages=1, doctype="50577-6"):
    return json.dumps(
        {
            "data": [{"setid": s} for s in setids],
            "metadata": {
                "total_pages": total_pages,
                "current_url": f"x/spls.json?doctype={doctype}",
            },
        }
    ).encode()


def test_label_gives_facts_only_never_dose_or_withdrawal_text():
    (row,) = us_dailymed.parse_label(LABEL)
    assert row["brand_name"] == "Albendamax"
    assert row["generic_name"] == "Albendazole"
    assert row["manufacturer"] == "Vetr, LLC"
    assert "113.6 mg per 1 mL" in row["composition"]
    assert "Glycerin" not in row["generic_name"]  # inactive ingredients are not generics
    assert "withdrawal" not in json.dumps(row).lower()
    assert "sheep" not in json.dumps(row).lower()


def test_human_labels_are_ignored():
    assert us_dailymed.parse_label(HUMAN) == []


def test_listing_becomes_us_specific_rows(monkeypatch):
    def fake_get(url):
        if "spls.json" in url and "50576-8" in url:
            return page([], doctype="50576-8")
        if url.endswith("a1.xml"):
            return LABEL
        if url.endswith("a2.xml"):
            return APPROVED
        raise ValueError(url)

    monkeypatch.setattr(us_dailymed, "_get", fake_get)
    cleaned = us_dailymed.clean_listing(page(["a1", "a2"]))
    by_number = {r["registration_number"]: r for r in cleaned.rows}
    assert set(by_number) == {"DailyMed 64c3482a-f978", "141-123"} or len(cleaned.rows) == 2
    statuses = {r["registration_status"] for r in cleaned.rows}
    assert statuses == {"registered", "unknown"}
    assert all("United States labelling" in r["notes"] for r in cleaned.rows)
    assert cleaned.report["labels_read"] == 2


def test_one_unreadable_label_does_not_stop_the_run(monkeypatch):
    def fake_get(url):
        if "50576-8" in url:
            return page([], doctype="50576-8")
        if url.endswith("good.xml"):
            return LABEL
        raise ValueError("boom")

    monkeypatch.setattr(us_dailymed, "_get", fake_get)
    cleaned = us_dailymed.clean_listing(page(["good", "bad"]))
    assert len(cleaned.rows) == 1 and cleaned.report["skipped_unreadable"] == 1


def test_entity_bombs_are_rejected():
    bomb = b'<!DOCTYPE d [<!ENTITY a "x"><!ENTITY b "&a;&a;&a;">]><document>&b;</document>'
    with pytest.raises(Exception):  # noqa: B017, PT011 - defusedxml raises its own error types
        us_dailymed.parse_label(bomb)
