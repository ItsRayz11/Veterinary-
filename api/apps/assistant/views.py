from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.schema import untyped_schema
from apps.core.throttling import UserThrottle

from . import interactions, service

DISCLAIMER = (
    "Answers are drawn only from reviewed records in this reference and are not clinical advice. "
    "Confirm every dose against the cited source and the product label."
)


class AssistantThrottle(UserThrottle):
    scope = "assistant"


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def interaction_check(request):
    slugs = request.query_params.get("generics", "").split(",")
    if len([s for s in slugs if s.strip()]) < 2:
        raise ValidationError({"generics": "Choose at least two drugs to compare."})
    return Response(interactions.check(slugs))


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AssistantThrottle])
def ask(request):
    try:
        result = service.ask(request.user, str(request.data.get("question", "")))
    except ValueError as exc:
        raise ValidationError({"question": str(exc)}) from exc
    return Response({**result, "disclaimer": DISCLAIMER}, status=http.HTTP_200_OK)
