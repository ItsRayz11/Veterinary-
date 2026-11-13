"""Tiny shared CRUD helper for staff APIs: validated, audited list/create/update views.

Fields are an explicit allow-list (never mass-assign), values are coerced by type, `full_clean`
runs the model's own validation, and every create/edit writes an AuditLog row listing the changed
field names and values (never secrets: fields named in `hidden` are logged by name only).
"""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import AuditLog
from .schema import untyped_schema


def coerce(model, name: str, value):
    f = model._meta.get_field(name)
    if isinstance(f, models.BooleanField):
        return bool(value)
    if isinstance(f, models.ForeignKey):
        if value in (None, ""):
            return None
        return f.related_model.objects.filter(pk=value).first() or _bad(name, "Unknown choice.")
    if isinstance(f, (models.IntegerField,)):
        try:
            return int(value) if value not in (None, "") or not f.null else None
        except (TypeError, ValueError):
            _bad(name, "Must be a whole number.")
    if isinstance(f, models.DecimalField):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            _bad(name, "Must be a number.")
    if isinstance(f, models.JSONField):
        return value
    if isinstance(f, models.DateTimeField | models.DateField):
        return value or None
    return "" if value is None else str(value).strip()


def _bad(name, msg):
    raise ValidationError({name: msg})


def apply(instance, fields, data, *, creating=False, create_only=()) -> list[str]:
    changed = []
    for name in fields:
        if name not in data or (name in create_only and not creating):
            continue
        v = coerce(type(instance), name, data[name])
        if getattr(instance, name) != v:
            setattr(instance, name, v)
            changed.append(name)
    return changed


def val(instance, name):
    v = getattr(instance, name)
    return v.pk if isinstance(v, models.Model) else (str(v) if v is not None else None)


def crud_views(
    model, *, fields, perm, row, name, create_only=(), hidden=(), on_create=None, after_save=None,
    queryset=None,
):  # fmt: skip
    """Returns (list_create_view, update_view); `name` prefixes the audit actions."""

    def audit(request, action, obj, before=None, after=None):
        mask = lambda d: {k: ("(set)" if k in hidden else v) for k, v in (d or {}).items()}  # noqa: E731
        AuditLog.objects.create(
            actor=request.user, action=f"{name}_{action}", object_type=obj._meta.label,
            object_id=str(obj.pk), before=mask(before) or None, after=mask(after) or None,
        )  # fmt: skip

    def list_create(request):
        if request.method == "GET":
            qs = queryset() if queryset else model.objects.all()
            return Response({"results": [row(o) for o in qs[:500]]})
        obj = model()
        try:
            apply(obj, fields, request.data, creating=True, create_only=create_only)
            if on_create:
                on_create(obj, request)
            obj.full_clean()
        except ValidationError as exc:
            return Response({"detail": "; ".join(exc.messages)}, status=http.HTTP_400_BAD_REQUEST)
        obj.save()
        if after_save:
            after_save(obj, request, True)
        audit(request, "created", obj, after={f: val(obj, f) for f in fields})
        return Response(row(obj), status=http.HTTP_201_CREATED)

    def update(request, pk):
        obj = model.objects.filter(pk=pk).first()
        if obj is None:
            return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
        before = {f: val(obj, f) for f in fields}
        try:
            changed = apply(obj, fields, request.data, create_only=create_only)
            obj.full_clean()
        except ValidationError as exc:
            return Response({"detail": "; ".join(exc.messages)}, status=http.HTTP_400_BAD_REQUEST)
        obj.save()
        if changed and after_save:
            after_save(obj, request, False)
        if changed:
            audit(
                request, "edited", obj,
                before={f: before[f] for f in changed},
                after={f: val(obj, f) for f in changed},
            )  # fmt: skip
        return Response(row(obj))

    # Distinct names keep OpenAPI operation ids unique (they derive from the view name).
    list_create.__name__, update.__name__ = f"{name}_list", f"{name}_update"
    wrap = lambda fn, methods: untyped_schema(  # noqa: E731
        api_view(methods)(permission_classes([perm])(fn))
    )
    return wrap(list_create, ["GET", "POST"]), wrap(update, ["PATCH"])


def simple_row(fields, extra=lambda o: {}):
    def row(o):
        d = {f: val(o, f) for f in fields}
        d["id"] = o.pk
        d.update(extra(o))
        return d

    return row
