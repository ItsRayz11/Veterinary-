from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .services import search


@api_view(["GET"])
@permission_classes([AllowAny])
def search_view(request):
    return Response(search(request.query_params.get("q", "")[:100]))
