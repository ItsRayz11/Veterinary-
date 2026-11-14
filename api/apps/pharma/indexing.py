"""Which catalogue pages search engines may index (see apps.countries.coverage).

Clinically reviewed records are always indexable. An official listing is indexable only when it
belongs to a country whose collection passed its coverage thresholds, so a half-filled country
never appears in search results as a thin site. Development data is never indexable."""

from django.db.models import BooleanField, Exists, ExpressionWrapper, OuterRef, Q

from apps.core.models import PUBLIC_STATUSES, ReviewStatus
from apps.countries.coverage import indexable_country_ids

from .models import Generic, Product, ProductRegistration

SIGNED = [ReviewStatus.EXPERT_REVIEWED, ReviewStatus.VERIFIED]
PUBLIC = [s.value for s in PUBLIC_STATUSES]


def _in_ready_country():
    return Exists(
        ProductRegistration.objects.filter(
            product=OuterRef("pk"),
            review_status__in=PUBLIC,
            country_id__in=indexable_country_ids(),
        )
    )


def annotate_indexable(qs):
    """Adds `indexable` (bool) to a Product, Generic or Company queryset."""
    model = qs.model
    if model is Product:
        ready = _in_ready_country()
    elif model is Generic:
        ready = Exists(
            Product.objects.filter(generic=OuterRef("pk")).filter(
                Exists(
                    ProductRegistration.objects.filter(
                        product=OuterRef("pk"),
                        review_status__in=PUBLIC,
                        country_id__in=indexable_country_ids(),
                    )
                )
            )
        )
    else:  # Company
        ready = Exists(
            Product.objects.filter(manufacturer=OuterRef("pk")).filter(
                Exists(
                    ProductRegistration.objects.filter(
                        product=OuterRef("pk"),
                        review_status__in=PUBLIC,
                        country_id__in=indexable_country_ids(),
                    )
                )
            )
        )
    return qs.annotate(_ready=ready).annotate(
        indexable=ExpressionWrapper(
            (Q(review_status__in=SIGNED) | (Q(review_status__in=PUBLIC) & Q(_ready=True)))
            & Q(is_development_data=False),
            output_field=BooleanField(),
        )
    )


def is_indexable(obj) -> bool:
    row = (
        annotate_indexable(type(obj).objects.filter(pk=obj.pk))
        .values_list("indexable", flat=True)
        .first()
    )
    return bool(row)
