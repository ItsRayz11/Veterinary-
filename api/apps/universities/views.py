from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.schema import untyped_schema
from apps.education.models import PastPaper
from apps.pharma.serializers import _status

from .models import University
from .serializers import UniversityBriefSerializer, UniversityDetailSerializer


class UniversityList(ListAPIView):
    """`?country=<iso2>` narrows the list."""

    permission_classes = [AllowAny]
    serializer_class = UniversityBriefSerializer

    def get_queryset(self):
        qs = University.objects.listed().select_related("country")
        country = self.request.query_params.get("country")
        if country:
            qs = qs.filter(country__iso2__iexact=country)
        return qs


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def university_detail(request, slug):
    uni = get_object_or_404(University.objects.listed().select_related("country"), slug=slug)
    papers = PastPaper.objects.filter(is_published=True, university__iexact=uni.name)
    return Response(
        {
            **UniversityDetailSerializer(uni).data,
            "status": _status(uni),
            "past_papers": [
                {
                    "course": p.course,
                    "degree": p.degree,
                    "year": p.year,
                    "exam_type": p.exam_type,
                    "url": p.legal_source_url,
                    "license_note": p.license_note,
                }
                for p in papers
            ],
        }
    )
