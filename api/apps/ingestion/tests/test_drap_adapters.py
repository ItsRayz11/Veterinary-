"""DRAP cleaners and the detail-carrying import path, using rows copied from the real public files."""

import pytest
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.countries.models import Country
from apps.ingestion import services
from apps.ingestion.adapters import drap
from apps.pharma.models import Product, ProductIngredient, ProductPack, ProductRegistration

# Verbatim rows from "31-List-of-Vet-Applications" (2025-06-13 download), shortened to a few rows.
APPLICATIONS = (
    "<strong>S.No.</strong>,<strong>Name and Address of Manufacturer</strong>,<strong>Brand Name</strong>,"
    '<strong>Composition</strong>,"<strong>Type of Form, Diary No and Date of Submission, Deposited Fee and Date</strong>"\n'
    '1,"M/s Mallard Pharmaceuticals Pvt Ltd.\n23km, Lahore Road, Multan, Pakistan",Ivermall 3.15% Injection 50ml,"Each 1ml Contains:\nIvermectin…31.5mg","Form-5 Dy.No 19514 dated 04-07-2022  Rs.30,000/- dated 23-06-2022"\n'
    '=A2+1,"M/s Mallard Pharmaceuticals Pvt Ltd.\n23km, Lahore Road, Multan, Pakistan",AR TNF Super Plus Powder,"Each 1gm Powder Contains:\nNeomycin Sulphate…150mg\nFlorfenicol…100mg\nOxytetracycline Hcl…300mg","Form-5 Dy.No 19517 dated 04-07-2022  Rs.30,000/- dated 23-06-2022"\n'
    '=A3+1,"M/s Mallard Pharmaceuticals Pvt Ltd.\n23km, Lahore Road, Multan, Pakistan",Doramall 1% Injection 50ml,"Each 1ml Contains:\nDoramectin…10mg","Form-5 Dy.No 19516 dated 04-07-2022  Rs.30,000/- dated 23-06-2022"\n'
    '=A4+1,"M/s Mallard Pharmaceuticals Pvt Ltd.\n23km, Lahore Road, Multan, Pakistan",Doramall 1% Injection 10ml,"Each 1ml Contains:\nDoramectin…10mg","Form-5 Dy.No 19515 dated 04-07-2022  Rs.30,000/- dated 23-06-2022"\n'
    '=A5+1,"M/s Star Laboratories Pvt Ltd.\n23-km, Multan Road, Lahore",Oxzym-P Injection 50ml,"Each ml Contains:\nOxytetracycline Hcl as Base…50mg\nPhenylbutazone…25mg\nMepyramine Maleate…25mg","Form-5 Dy.No 6355 dated 06-03-2023 Rs.30,000/- dated 01-03-2023"\n'
    '=A6+1,"M/s Test Vitamins Ltd.\nLahore",Vita Mix Injection 100ml,"Each 100ml Contains:\nRiboflavin Sodium Phosphate...0.17mg\nVitamin B12…<span style=""color:#000000;"">500µg</span>\nMystery Extract…some amount","Form-5 Dy.No 7 dated 01-01-2023 Rs.30,000/- dated 01-01-2023"\n'
)

BIOLOGICALS = (
    "Sr.,Applicant,Applied Product,Application Date,Manufacturer,Origin,Remarks\n"
    '1.              ,"Fartal Pharmaceuticals, Karachi","Virus vaccine from the strain ""La-Sota"" against Newcastle disease dry",7-Jan-21,'
    '"Federal State Enterprise ""Shchelkovo Biocombinat"", Moscow oblast, Russia",Import,Evaluated. Short comings communicated to the firm.\n'
    '2.              ,"NIRAAV PHARMA PVT LTD, Karachi",MEILAN K. ND + H9,26-Jan-21,"Meilan Biological, Henan, China",Import,Evaluated.\n'
    '3.              ,"NIRAAV PHARMA PVT LTD, Karachi",MEILAN K. ND + H9,26-Jan-21,"Meilan Biological, Henan, China",import,Duplicate line.\n'
)


def by_brand(cleaned, brand):
    return next(r for r in cleaned.rows if r["brand_name"] == brand)


def test_company_names_are_cleaned_and_addresses_kept_separately():
    name, address = drap.clean_company(
        "M/s Mallard Pharmaceuticals Pvt Ltd.\n23km, Lahore Road, Multan, Pakistan"
    )
    assert (
        name == "Mallard Pharmaceuticals Pvt Ltd"
        and address == "23km, Lahore Road, Multan, Pakistan"
    )


def test_strengths_units_and_basis_are_read_exactly():
    cleaned = drap.clean_vet_applications(APPLICATIONS)
    iver = by_brand(cleaned, "Ivermall 3.15% Injection")
    assert iver["generic_name"] == "Ivermectin"
    assert iver["ingredients"] == [
        {"name": "Ivermectin", "value": "31.5", "unit": "mg", "per_value": "1", "per_unit": "mL"}
    ]
    tnf = by_brand(cleaned, "AR TNF Super Plus Powder")
    assert tnf["generic_name"] == "Florfenicol + Neomycin Sulphate + Oxytetracycline Hydrochloride"
    assert {(i["name"], i["value"], i["unit"], i["per_unit"]) for i in tnf["ingredients"]} == {
        ("Neomycin Sulphate", "150", "mg", "g"),
        ("Florfenicol", "100", "mg", "g"),
        ("Oxytetracycline Hydrochloride", "300", "mg", "g"),
    }


def test_pack_variants_merge_into_one_product_with_two_packs():
    cleaned = drap.clean_vet_applications(APPLICATIONS)
    dora = [r for r in cleaned.rows if r["brand_name"] == "Doramall 1% Injection"]
    assert len(dora) == 1
    assert dora[0]["packs"] == [
        {"size": "50", "unit": "mL", "form": "injection"},
        {"size": "10", "unit": "mL", "form": "injection"},
    ]
    assert cleaned.report["source_rows"] == 6 and cleaned.report["products"] == 5


def test_messy_rows_html_micro_sign_three_dots_and_unreadable_strengths():
    row = by_brand(drap.clean_vet_applications(APPLICATIONS), "Vita Mix Injection")
    got = {i["name"]: (i["value"], i["unit"]) for i in row["ingredients"]}
    assert got == {"Riboflavin Sodium Phosphate": ("0.17", "mg"), "Vitamin B12": ("500", "mcg")}
    # the strength that could not be read is not invented: it stays in the source's own text
    assert "Mystery Extract" in row["generic_name"] and "some amount" in row["composition"]
    assert "<span" not in row["composition"]


def test_nothing_is_ever_marked_registered():
    cleaned = drap.clean_vet_applications(APPLICATIONS)
    assert all(r["registration_number"] == "" for r in cleaned.rows)
    assert all("not a registration" in r["notes"] for r in cleaned.rows)
    assert "Form-5" in cleaned.rows[0]["notes"] and "19514" in cleaned.rows[0]["notes"]


def test_mega_units_and_long_combinations():
    assert drap.parse_strength("2MIU") == ("2000000", "IU")
    assert drap.parse_strength("500µg") == ("500", "mcg")
    assert drap.parse_strength("about 5") is None and drap.parse_strength("5 parsecs") is None
    names = [f"Ingredient number {i}" for i in range(30)]
    long_name = drap.generic_name_for(names)
    assert len(long_name) <= 190 and long_name.endswith("]")
    assert long_name != drap.generic_name_for(
        names[:-1] + ["Different one"]
    )  # hash keeps them apart


def test_biologicals_use_the_applicant_and_a_placeholder_generic():
    cleaned = drap.clean_vet_biologicals(BIOLOGICALS)
    assert cleaned.report["products"] == 2 and cleaned.report["duplicates_merged"] == 1
    first = cleaned.rows[0]
    assert first["manufacturer"] == "Fartal Pharmaceuticals" and first["company_role"] == "importer"
    assert first["is_biologic"] == "true" and "not yet classified" in first["generic_name"]
    assert "Shchelkovo" in first["notes"] and "Russia" in first["notes"]


# ---------- through the import pipeline ----------


@pytest.fixture
def env(db):
    call_command("seed_reference")
    return {
        "user": User.objects.create_user("importer", password="x", role=Role.EDITOR),
        "pk": Country.objects.get(iso2="PK"),
    }


SOURCE = {"title": "DRAP list (test)", "publisher": "DRAP", "license_note": "Test note"}


def load(env, cleaned):
    batch = services.stage_batch(
        user=env["user"], country=env["pk"], source_data=SOURCE, csv_text=drap.to_csv(cleaned.rows)
    )
    while services.approve_clean(batch, env["user"])["remaining"]:
        pass
    return batch


def test_import_creates_unreviewed_products_with_strengths_and_packs_and_no_registration(env):
    load(env, drap.clean_vet_applications(APPLICATIONS))
    dora = Product.objects.get(brand_name="Doramall 1% Injection")
    assert dora.review_status == "needs_verification" and not dora.is_public
    strength = ProductIngredient.objects.get(product=dora)
    assert (f"{strength.strength_value.normalize():f}", strength.strength_unit.code) == ("10", "mg")
    assert (strength.per_unit.code, f"{strength.per_value.normalize():f}") == ("mL", "1")
    packs = {
        (f"{p.pack_size_value.normalize():f}", p.pack_size_unit.code)
        for p in ProductPack.objects.filter(product=dora)
    }
    assert packs == {("50", "mL"), ("10", "mL")}
    assert "not a registration" in dora.description and "Doramectin" in dora.description
    assert dora.manufacturer.description.startswith("Address as listed by the source: 23km")
    assert ProductRegistration.objects.count() == 0  # applications never become registrations
    assert dora.generic.ingredients.filter(name="Doramectin").exists()


def test_mixed_readability_product_keeps_source_text_and_flags_it(env):
    load(env, drap.clean_vet_applications(APPLICATIONS))
    vita = Product.objects.get(brand_name="Vita Mix Injection")
    assert ProductIngredient.objects.filter(product=vita).count() == 2  # only the readable ones
    assert "some amount" in vita.description


def test_biologicals_load_as_importer_companies_and_biologic_products(env):
    load(env, drap.clean_vet_biologicals(BIOLOGICALS))
    product = Product.objects.get(brand_name="MEILAN K. ND + H9")
    assert product.is_biologic and product.category == "Veterinary biological"
    assert product.manufacturer.is_importer and not product.manufacturer.is_manufacturer
    assert "Meilan Biological" in product.description


def test_csv_detail_columns_must_be_valid_json_lists():
    from django.core.exceptions import ValidationError

    header = "brand_name,generic_name,manufacturer,ingredients\n"
    with pytest.raises(ValidationError, match="JSON list"):
        services.parse_csv(header + 'A,B,C,"not json"\n')
    with pytest.raises(ValidationError, match="list of objects"):
        services.parse_csv(header + 'A,B,C,"[1, 2]"\n')
    assert services.parse_csv(header + 'A,B,C,"[]"\n')[0]["ingredients"] == []
