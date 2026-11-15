from rest_framework import serializers

from apps.pharma.serializers import _status

from .models import University


def _stored_url(obj) -> str:
    """Public R2 URL of the stored copy, when one exists and R2 serves a public base URL."""
    from django.contrib.contenttypes.models import ContentType

    from apps.automation import r2
    from apps.automation.models import ImageAsset, ImageStatus

    if not r2.public_url_for("x"):
        return ""
    asset = (
        ImageAsset.objects.filter(
            content_type=ContentType.objects.get_for_model(obj),
            object_id=obj.pk,
            original_url=obj.image_url,
            status=ImageStatus.STORED,
        )
        .exclude(object_key="")
        .first()
    )
    return r2.public_url_for(asset.object_key) if asset else ""


def _image(obj) -> dict | None:
    if not obj.image_url:
        return None
    return {
        "url": _stored_url(obj) or obj.image_url,
        "page_url": obj.image_page_url,
        "credit": obj.image_credit,
        "license": obj.image_license,
        "license_url": obj.image_license_url,
    }


class UniversityBriefSerializer(serializers.ModelSerializer):
    country = serializers.CharField(source="country.iso2")
    country_name = serializers.CharField(source="country.name")
    status = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = University
        fields = ("name", "slug", "country", "country_name", "city", "image", "status")

    def get_status(self, obj) -> dict:
        return _status(obj)

    def get_image(self, obj) -> dict | None:
        return _image(obj)


class UniversityDetailSerializer(UniversityBriefSerializer):
    class Meta(UniversityBriefSerializer.Meta):
        fields = (
            *UniversityBriefSerializer.Meta.fields,
            "website",
            "summary",
            "founded_year",
            "latitude",
            "longitude",
            "source_url",
            "source_license",
            "wikidata_id",
        )
