from rest_framework import serializers

from apps.clinical.models import ClinicalNote, DoseRegimen, WithdrawalPeriod
from apps.companies.models import Company
from apps.core.models import ReviewStatus

from .models import Generic, Product


def _status(obj) -> dict:
    return {
        "code": obj.review_status,
        "label": ReviewStatus(obj.review_status).label,
        "is_development_data": obj.is_development_data,
        "reviewed_at": obj.reviewed_at,
    }


def source_payload(pairs) -> list[dict]:
    return [
        {
            "id": s.pk,
            "title": s.title,
            "publisher": s.publisher,
            "url": s.url,
            "doi": s.doi,
            "type": s.source_type,
            "publication_date": s.publication_date,
            "locator": locator,
        }
        for s, locator in pairs
    ]


class CompanyBriefSerializer(serializers.ModelSerializer):
    country = serializers.CharField(source="country.iso2")

    class Meta:
        model = Company
        fields = ("name", "slug", "country")


class ProductBriefSerializer(serializers.ModelSerializer):
    manufacturer = CompanyBriefSerializer()
    generic = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    generic_name = serializers.CharField(source="generic.name")
    countries = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "brand_name",
            "slug",
            "generic",
            "generic_name",
            "manufacturer",
            "countries",
            "status",
        )

    def get_countries(self, obj):
        # uses the prefetch; no extra queries
        return sorted({r.country.iso2 for r in obj.registrations.all()})

    def get_status(self, obj):
        return _status(obj)


class DoseSerializer(serializers.ModelSerializer):
    species = serializers.CharField(source="species.slug")
    species_name = serializers.CharField(source="species.name")
    indication = serializers.CharField(source="indication.name", default=None)
    route = serializers.CharField(source="route.code")
    dose_unit = serializers.CharField(source="dose_unit.code")
    max_single_dose_unit = serializers.CharField(source="max_single_dose_unit.code", default=None)
    country = serializers.CharField(source="country.iso2", default=None)
    status = serializers.SerializerMethodField()
    calculator_ready = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()

    class Meta:
        model = DoseRegimen
        fields = (
            "id",
            "species",
            "species_name",
            "indication",
            "route",
            "country",
            "dose_min",
            "dose_max",
            "dose_unit",
            "interval_hours",
            "duration_min_days",
            "duration_max_days",
            "max_single_dose",
            "max_single_dose_unit",
            "notes",
            "status",
            "calculator_ready",
            "sources",
        )

    def get_status(self, obj):
        return _status(obj)

    def get_calculator_ready(self, obj):
        return obj.is_calculator_ready

    def get_sources(self, obj):
        return source_payload(self.context["sources"].get(obj.pk, []))


class NoteSerializer(serializers.ModelSerializer):
    species = serializers.CharField(source="species.slug", default=None)
    status = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()

    class Meta:
        model = ClinicalNote
        fields = ("id", "kind", "species", "text", "status", "sources")

    def get_status(self, obj):
        return _status(obj)

    def get_sources(self, obj):
        return source_payload(self.context["note_sources"].get(obj.pk, []))


class WithdrawalSerializer(serializers.ModelSerializer):
    product = serializers.CharField(source="product.brand_name")
    country = serializers.CharField(source="country.iso2")
    species = serializers.CharField(source="species.slug")
    commodity = serializers.CharField(source="commodity.name")
    route = serializers.CharField(source="route.code")
    status = serializers.SerializerMethodField()

    class Meta:
        model = WithdrawalPeriod
        fields = (
            "product",
            "country",
            "species",
            "commodity",
            "route",
            "duration_value",
            "duration_unit",
            "regimen_note",
            "regulatory_status",
            "status",
        )

    def get_status(self, obj):
        return _status(obj)


class GenericListSerializer(serializers.ModelSerializer):
    drug_class = serializers.CharField(source="drug_class.name", default=None)

    class Meta:
        model = Generic
        fields = ("name", "slug", "drug_class")


class GenericDetailSerializer(serializers.ModelSerializer):
    drug_class = serializers.CharField(source="drug_class.name", default=None)
    synonyms = serializers.SlugRelatedField(many=True, slug_field="synonym", read_only=True)
    ingredients = serializers.SlugRelatedField(many=True, slug_field="name", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Generic
        fields = (
            "name",
            "slug",
            "drug_class",
            "synonyms",
            "ingredients",
            "description",
            "mechanism",
            "status",
        )

    def get_status(self, obj):
        return _status(obj)
