from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.accounts.models import Role, User
from apps.clinical.models import Commodity, DoseRegimen, Interaction, Route, WithdrawalPeriod
from apps.core import review as services
from apps.core.models import AuditLog, ReviewStatus
from apps.countries.models import Country
from apps.pharma.models import Generic, Product
from apps.sources.models import Source, SourceLink
from apps.species.models import Species
from apps.units.models import Unit


@pytest.fixture
def ctx(db):
    call_command("seed_dev_catalog")
    generic = Generic.objects.get(slug="enrofloxacin")
    generic.is_development_data = False  # a real-looking generic for status transitions
    generic.save()
    return {
        "generic": generic,
        "product": Product.objects.first(),
        "species": Species.objects.get(slug="cattle"),
        "route": Route.objects.create(code="IM", name="Intramuscular"),
        "unit": Unit.objects.get(code="mg/kg"),
        "country": Country.objects.get(iso2="PK"),
    }


def make_dose(ctx, **kw):
    fields = dict(
        generic=ctx["generic"],
        species=ctx["species"],
        route=ctx["route"],
        dose_unit=ctx["unit"],
        dose_min=Decimal("1"),
        dose_max=Decimal("2"),
        is_development_data=True,
    )
    fields.update(kw)
    return DoseRegimen.objects.create(**fields)


def attach_source(obj):
    s = Source.objects.create(source_type="other", title="Test source", url="https://example.org")
    from django.contrib.contenttypes.models import ContentType

    SourceLink.objects.create(
        source=s, content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
    )


def reviewer(username="vet"):
    return User.objects.create_user(username, password="x", role=Role.VET_REVIEWER)


def test_dose_range_constraints(ctx):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_dose(ctx, dose_min=Decimal("5"), dose_max=Decimal("2"))
    with pytest.raises(IntegrityError), transaction.atomic():
        make_dose(ctx, dose_min=Decimal("0"))


def test_dose_unit_must_be_dose_rate(ctx):
    d = make_dose(ctx, dose_unit=Unit.objects.get(code="mg"))
    with pytest.raises(ValidationError):
        d.clean()


def test_cannot_publish_without_source(ctx):
    d = make_dose(ctx, is_development_data=False)
    with pytest.raises(ValidationError):
        services.set_review_status(d, ReviewStatus.VERIFIED, reviewer())


def test_only_vet_reviewer_can_verify(ctx):
    d = make_dose(ctx, is_development_data=False)
    attach_source(d)
    editor = User.objects.create_user("ed", password="x", role=Role.EDITOR)
    with pytest.raises(PermissionDenied):
        services.set_review_status(d, ReviewStatus.VERIFIED, editor)
    services.set_review_status(d, ReviewStatus.VERIFIED, reviewer())
    d.refresh_from_db()
    assert d.review_status == ReviewStatus.VERIFIED and d.reviewed_at
    assert AuditLog.objects.filter(action="review_status_changed").count() == 1


def test_no_self_approval(ctx):
    vet = reviewer()
    d = make_dose(ctx, is_development_data=False, submitted_by=vet)
    attach_source(d)
    with pytest.raises(PermissionDenied):
        services.set_review_status(d, ReviewStatus.VERIFIED, vet)


def test_dev_data_cannot_be_signed_off(ctx):
    d = make_dose(ctx)
    attach_source(d)
    with pytest.raises(ValidationError):
        services.set_review_status(d, ReviewStatus.VERIFIED, reviewer())


def test_calculator_only_sees_reviewed_doses(ctx):
    d = make_dose(ctx, is_development_data=False)
    assert DoseRegimen.objects.calculator_ready().count() == 0
    attach_source(d)
    services.set_review_status(d, ReviewStatus.VERIFIED, reviewer())
    assert DoseRegimen.objects.calculator_ready().count() == 1


def test_manufacturer_supplied_dose_is_not_calculator_ready(ctx):
    d = make_dose(ctx, is_development_data=False)
    attach_source(d)
    services.set_review_status(
        d,
        ReviewStatus.MANUFACTURER_SUPPLIED,
        User.objects.create_user("e2", password="x", role=Role.EDITOR),
    )
    assert DoseRegimen.objects.public().count() == 1
    assert DoseRegimen.objects.calculator_ready().count() == 0


def test_withdrawal_unique_per_context_and_strict_public(ctx):
    milk = Commodity.objects.create(slug="milk", name="Milk")
    kw = dict(
        product=ctx["product"],
        country=ctx["country"],
        species=ctx["species"],
        commodity=milk,
        route=ctx["route"],
        duration_value=Decimal("4"),
        duration_unit="days",
    )
    w = WithdrawalPeriod.objects.create(**kw)
    with pytest.raises(IntegrityError), transaction.atomic():
        WithdrawalPeriod.objects.create(**kw)
    assert w.duration_hours == 96
    attach_source(w)
    services.set_review_status(
        w,
        ReviewStatus.MANUFACTURER_SUPPLIED,
        User.objects.create_user("e3", password="x", role=Role.EDITOR),
    )
    assert WithdrawalPeriod.objects.public().count() == 0  # manufacturer-supplied is not enough


def test_interaction_pair_is_ordered_and_unique(ctx):
    other = Generic.objects.create(name="Other drug")
    i = Interaction.create_pair(other, ctx["generic"], severity="major", description="x")
    assert i.generic_a_id < i.generic_b_id
    with pytest.raises(IntegrityError), transaction.atomic():
        Interaction.create_pair(ctx["generic"], other, severity="minor", description="y")
    with pytest.raises(ValueError):
        Interaction.create_pair(other, other, severity="minor", description="z")
