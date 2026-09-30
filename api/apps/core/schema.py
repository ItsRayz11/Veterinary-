"""OpenAPI helpers for function-based views that return plain JSON built by hand."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

_METHODS = ("get", "post", "put", "patch", "delete")


def untyped_schema(view):
    """Document the endpoint (path, method, auth, throttling) with a generic JSON body.

    Keeps /api/schema/ complete until per-endpoint serializers are written. Operation ids are
    `<app>_<view name>` (plus `_<method>` when a view serves several methods), so they are
    unique and stable for client generators.
    """
    cls = getattr(view, "cls", view)
    app = view.__module__.split(".")[1] if view.__module__.count(".") >= 2 else view.__module__
    base = f"{app}_{cls.__name__}"
    methods = [m for m in _METHODS if hasattr(cls, m)]
    if len(methods) <= 1:
        return extend_schema(
            operation_id=base, request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT
        )(view)
    for m in methods:
        view = extend_schema(
            methods=[m.upper()],
            operation_id=f"{base}_{m}",
            request=OpenApiTypes.OBJECT,
            responses=OpenApiTypes.OBJECT,
        )(view)
    return view
